import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from openai import OpenAI

from config import settings
from auth import get_current_user
from api.routers.system import get_engine
from db.db_manager import SessionLocal
from db.models import AlertModel
from sqlalchemy import desc

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/copilot",
    tags=["copilot"],
    responses={404: {"description": "Not found"}},
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

# Define tools for Moonshot
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "获取当前网络入侵检测系统(NIDS)的运行状态、已加载的模型名称、以及处理的流量包统计信息。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_alerts",
            "description": "获取系统最近产生的真实网络攻击告警信息，用于向用户汇报当前面临的安全威胁态势。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "获取最近几条告警，默认 5 条，最多 20 条。"
                    }
                },
                "required": []
            }
        }
    }
]

SYSTEM_PROMPT = """你是一个名为 NIDS-Copilot 的高级网络安全专家。你的职责是协助用户进行入侵检测系统（NIDS）的运营。

【本系统（你的宿主）核心知识库】：
本系统是一个基于前后端分离（Vue3 + FastAPI）的网络入侵检测系统。
1. **模型训练模块（Training）**：
   - 位于左侧菜单的“模型训练”。
   - 操作步骤：用户先在“数据集管理”中上传或使用“类别平衡器”平衡数据（支持大类截断、小类时序原位复制）。然后回到训练页面，选择模型类型（支持 LightGBM, XGBoost, Random Forest, 1D-CNN, CNN-ResAttn, GRU, Transformer 等），选择数据集，点击训练。
   - 特点：模型使用 78 维特征（已删除 IP/Port 等强标识符以防过拟合，保留了目的端口的语义）。
   - 注意：模型名称建议使用英文、数字、下划线或连字符，避免使用中文，以确保模型文件在 Windows 环境下正常加载。
2. **实验与融合模块（Experiments）**：
   - 位于左侧菜单的“实验模块”。
   - 操作步骤：用户勾选多个模型（至少两个），系统会使用“动态软投票（Dynamic Soft Voting）”策略训练一个强大的融合模型（fusion.joblib）。
3. **总体模型评估模块（Model Evaluation）**：
   - 位于左侧菜单的“模型评估”。
   - 功能：对已训练好的单个模型进行全面的性能评估，支持选择多个 CSV 数据集文件进行批量测试。
   - 操作步骤：选择要评估的模型 → 选择一个或多个带标签的 CSV 数据集 → 设置批次大小 → 开始评估。
   - 输出指标：Accuracy, Precision, Recall, F1, Macro-F1, FPR, FNR, 混淆矩阵, 各类别详细指标, 预测分布等。
   - 支持导出 Excel 格式的评估报告，包含图表和详细分析。
   - 注意：当前仅支持 CIC-IDS2017 体系模型，不支持 NSL-KDD 体系模型。
4. **实时检测引擎（Dashboard/System）**：
   - 用户在 Dashboard 选择训练好的模型并点击“启动引擎”。
   - 引擎启动后，会使用 `flow_aggregator.py` 实时提取网卡或 PCAP 回放的 78 维特征，进行预测。
   - 包含防告警风暴机制：15秒冷却，30秒超时。重复攻击不会无限弹窗，而是增加 repeat_count。
5. **安全态势与报表（Alerts）**：
   - 告警管理页面支持查看历史告警，并支持一键导出 CSV 和带图表的 PDF 态势分析报告。

【你的行为准则】：
1. 如果用户询问操作指南，请**严格基于上述系统知识库**，提供清晰的 Markdown 步骤。
2. 如果用户询问系统状态或告警情况，请**必须调用提供的工具**获取最新数据，然后再进行回答。不要凭空捏造数据！
3. 针对具体的攻击告警，请结合你的安全知识，给出专业的处置建议（如封禁IP、修改配置等）。
4. 保持对话简洁专业，不要输出无关内容。你没有修改系统的权限，只能提供查询和建议。
"""

def fetch_system_status(engine) -> str:
    """Tool implementation: fetch system status"""
    status_info = {
        "is_running": engine.state.value if hasattr(engine, 'state') else "unknown",
        "current_model": engine.current_model_name if hasattr(engine, 'current_model_name') else "none",
        "stats": engine.stats if hasattr(engine, 'stats') else {}
    }
    return json.dumps(status_info, ensure_ascii=False)

def fetch_recent_alerts(engine, limit: int = 5) -> str:
    """Tool implementation: fetch recent alerts from alert engine (with eventification)"""
    try:
        alerts = engine.alert_engine.get_alerts(limit=limit)
        result = []
        for a in alerts:
            result.append({
                "id": a["id"],
                "timestamp": str(a["timestamp"]),
                "source_ip": a["src_ip"],
                "destination_ip": a["dst_ip"],
                "attack_type": a["attack_type"],
                "confidence": a["confidence"],
                "repeat_count": a.get("repeat_count", 1)
            })
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error fetching alerts for copilot: {e}")
        return json.dumps([])

@router.post("/chat")
async def copilot_chat(
    request: ChatRequest,
    current_user: Any = Depends(get_current_user),
    engine: Any = Depends(get_engine)
):
    if not settings.MOONSHOT_API_KEY or settings.MOONSHOT_API_KEY.startswith("sk-xxxx"):
        return {
            "message": {"role": "assistant", "content": "⚠️ 系统未配置 Moonshot API Key。请在后端 `config.py` 中配置有效的 `MOONSHOT_API_KEY` 后再使用智能助手。"}
        }

    try:
        client = OpenAI(
            api_key=settings.MOONSHOT_API_KEY,
            base_url=settings.MOONSHOT_BASE_URL,
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        # 1. Send messages and tools to Moonshot
        response = client.chat.completions.create(
            model=settings.MOONSHOT_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # 2. Check if model wants to call tools
        if tool_calls:
            # Append the model's response to the conversation
            messages.append(response_message)
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Execute tool
                if function_name == "get_system_status":
                    tool_result = fetch_system_status(engine)
                elif function_name == "get_recent_alerts":
                    limit = function_args.get("limit", 5)
                    tool_result = fetch_recent_alerts(engine, min(limit, 20))
                else:
                    tool_result = json.dumps({"error": f"Unknown tool: {function_name}"})
                
                # Append tool result to conversation
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_result,
                })
            
            # 3. Second call to Moonshot with tool results
            second_response = client.chat.completions.create(
                model=settings.MOONSHOT_MODEL,
                messages=messages,
            )
            return {"message": {"role": "assistant", "content": second_response.choices[0].message.content}}

        # If no tool calls, just return the response
        return {"message": {"role": "assistant", "content": response_message.content}}

    except Exception as e:
        logger.error(f"Moonshot API error: {e}", exc_info=True)
        return {"message": {"role": "assistant", "content": f"抱歉，与 AI 助手通信时出现错误: {str(e)}"}}
