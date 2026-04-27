from fastapi import APIRouter, HTTPException, Depends, Request, Query
from auth import get_current_user, TokenData
from typing import List, Optional, Dict, Any
from ml.detection_engine import DetectionEngine
from ml.false_positive_manager import FalsePositiveManager, GovernanceRule
from pydantic import BaseModel
from datetime import datetime, timedelta
import random

router = APIRouter()

# FP Manager instance
_fp_manager: Optional[FalsePositiveManager] = None

def get_fp_manager() -> FalsePositiveManager:
    global _fp_manager
    if _fp_manager is None:
        _fp_manager = FalsePositiveManager()
    return _fp_manager

def get_engine(request: Request) -> DetectionEngine:
    return request.app.state.engine

class AlertOut(BaseModel):
    id: int
    timestamp: datetime
    src_ip: str
    dst_ip: str
    protocol: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    attack_type: str
    confidence: float
    is_false_positive: bool
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    repeat_count: int = 1
    event_status: str = "active"
    duration_seconds: int = 0
    
    class Config:
        from_attributes = True

class AlertDetailOut(BaseModel):
    id: int
    timestamp: datetime
    src_ip: str
    dst_ip: str
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    attack_type: str
    confidence: float
    is_false_positive: bool
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    repeat_count: int = 1
    event_status: str = "active"
    duration_seconds: int = 0
    raw_features: Optional[dict] = None
    shap_analysis: Optional[dict] = None
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[AlertOut])
async def get_alerts(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get recent alerts"""
    return engine.alert_engine.get_alerts(limit=limit, skip=skip)

from fastapi.responses import StreamingResponse
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
import collections

@router.get("/export-report")
async def export_alerts_report(
    format: str = Query("excel", description="Export format: excel or pdf"),
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Export alerts statistics report"""
    try:
        # 使用 detection engine 获取带事件化装饰的完整告警数据（和前端表格一致）
        alerts = engine.alert_engine.get_alerts(limit=10000)
        if not alerts:
            raise HTTPException(status_code=404, detail="No alerts data available to export")
            
        # 统计数据
        total_alerts = len(alerts)
        attack_dist = collections.Counter([a.get("attack_type", "Unknown") for a in alerts])
        src_ip_dist = collections.Counter([a.get("src_ip", "0.0.0.0") for a in alerts])
        
        if format.lower() in ["csv", "excel"]:
            # CSV 无法直接插入图表，所以强制使用 Excel 引擎来生成带条形图的报表
            df = pd.DataFrame([{
                "ID": a["id"],
                "Time": a["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(a["timestamp"], datetime) else a["timestamp"],
                "Source IP": a["src_ip"],
                "Destination IP": a["dst_ip"],
                "Protocol": a["protocol"],
                "Attack Type": a["attack_type"],
                "Repeat Count": a.get("repeat_count", 1),
                "Last Seen": a["last_seen"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(a.get("last_seen"), datetime) else a.get("last_seen", ""),
                "Event Status": a.get("event_status", "active"),
                "Confidence": f"{a['confidence']:.2f}",
                "Is False Positive": a["is_false_positive"]
            } for a in alerts])
            
            stream = io.BytesIO()
            # 使用 xlsxwriter 引擎生成带彩色条形图的 Excel
            with pd.ExcelWriter(stream, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Alerts', index=False)
                
                workbook = writer.book
                worksheet = writer.sheets['Alerts']
                
                # 调整列宽
                worksheet.set_column('B:B', 20)
                worksheet.set_column('C:D', 15)
                worksheet.set_column('F:F', 20)
                worksheet.set_column('H:H', 20)
                
                # 写入统计数据用于生成图表
                summary_sheet = workbook.add_worksheet('Summary')
                summary_sheet.write_row('A1', ['Attack Type', 'Count'])
                row = 1
                for k, v in attack_dist.most_common():
                    summary_sheet.write_row(row, 0, [k, v])
                    row += 1
                    
                # 创建彩色条形图 (Bar Chart)
                chart = workbook.add_chart({'type': 'column'})
                
                # 给不同的柱子设置多种颜色
                colors_list = ['#FF9900', '#3366CC', '#109618', '#990099', '#DC3912', '#3B3EAC', '#0099C6', '#DD4477', '#66AA00', '#B82E2E']
                points = [{'fill': {'color': colors_list[i % len(colors_list)]}} for i in range(row - 1)]
                
                chart.add_series({
                    'name': 'Attack Count',
                    'categories': ['Summary', 1, 0, row - 1, 0],
                    'values':     ['Summary', 1, 1, row - 1, 1],
                    'points': points
                })
                chart.set_title({'name': 'Attack Type Distribution'})
                chart.set_x_axis({'name': 'Attack Type'})
                chart.set_y_axis({'name': 'Count'})
                chart.set_legend({'none': True})
                
                # 将图表插入到主表
                worksheet.insert_chart('M2', chart, {'x_scale': 1.2, 'y_scale': 1.2})
                
            stream.seek(0)
            response = StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response.headers["Content-Disposition"] = 'attachment; filename="alerts_report.xlsx"'
            return response
            
        elif format.lower() == "pdf":
            # 生成 PDF 并带上扇形饼图
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = styles['Heading1']
            title_style.alignment = 1 # Center
            
            elements.append(Paragraph("NIDS Security Alerts Report", title_style))
            elements.append(Spacer(1, 12))
            
            elements.append(Paragraph(f"Total Alerts Detected: {total_alerts}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # 添加饼图 (Pie Chart)
            elements.append(Paragraph("Attack Type Distribution Chart", styles['Heading2']))
            elements.append(Spacer(1, 6))
            
            drawing = Drawing(400, 200)
            pc = Pie()
            pc.x = 100
            pc.y = 20
            pc.width = 150
            pc.height = 150
            
            labels = []
            data = []
            # PDF 饼图只展示前 6 种最多的攻击，其他的归为 Others
            common_attacks = attack_dist.most_common(6)
            for k, v in common_attacks:
                labels.append(f"{k} ({v})")
                data.append(v)
            
            pc.data = data
            pc.labels = labels
            pc.slices.strokeWidth = 0.5
            
            color_palette = [colors.HexColor('#FF9900'), colors.HexColor('#3366CC'), colors.HexColor('#109618'), 
                             colors.HexColor('#990099'), colors.HexColor('#DC3912'), colors.HexColor('#3B3EAC')]
            for i, col in enumerate(color_palette):
                if i < len(pc.data):
                    pc.slices[i].fillColor = col
                    
            drawing.add(pc)
            elements.append(drawing)
            elements.append(Spacer(1, 20))
            
            # 攻击分布表格
            elements.append(Paragraph("Attack Type Details", styles['Heading2']))
            data_table = [["Attack Type", "Count"]]
            for k, v in attack_dist.most_common():
                data_table.append([str(k), str(v)])
                
            t = Table(data_table, colWidths=[200, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))
            
            # Top IP 表格
            elements.append(Paragraph("Top 10 Source IPs", styles['Heading2']))
            ip_data = [["Source IP", "Count"]]
            for k, v in src_ip_dist.most_common(10):
                ip_data.append([str(k), str(v)])
            t_ip = Table(ip_data, colWidths=[200, 100])
            t_ip.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t_ip)
            
            doc.build(elements)
            buffer.seek(0)
            
            response = StreamingResponse(buffer, media_type="application/pdf")
            response.headers["Content-Disposition"] = 'attachment; filename="alerts_report.pdf"'
            return response
            
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'excel' or 'pdf'")
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{alert_id}", response_model=AlertDetailOut)
async def get_alert_detail(
    alert_id: int,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get alert detail"""
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    db = SessionLocal()
    try:
        rec = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Alert not found")
        # Extract shap if present in raw_features
        shap_analysis = None
        if rec.raw_features and isinstance(rec.raw_features, dict):
            shap_analysis = rec.raw_features.get("shap_analysis")
        decorated = engine.alert_engine._decorate_alert_dict(rec)
        return AlertDetailOut(
            id=rec.id,
            timestamp=rec.timestamp,
            src_ip=rec.src_ip,
            dst_ip=rec.dst_ip,
            src_port=rec.src_port,
            dst_port=rec.dst_port,
            protocol=rec.protocol,
            attack_type=rec.attack_type,
            confidence=rec.confidence,
            is_false_positive=rec.is_false_positive,
            first_seen=decorated.get("first_seen"),
            last_seen=decorated.get("last_seen"),
            repeat_count=decorated.get("repeat_count", 1),
            event_status=decorated.get("event_status", "active"),
            duration_seconds=decorated.get("duration_seconds", 0),
            raw_features=rec.raw_features,
            shap_analysis=shap_analysis
        )
    finally:
        db.close()

@router.post("/{alert_id}/false_positive")
async def mark_false_positive(
    alert_id: int,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Mark alert as false positive"""
    success = engine.alert_engine.mark_false_positive(alert_id, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert marked as false positive"}

@router.post("/{alert_id}/unmark_false_positive")
async def unmark_false_positive(
    alert_id: int,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Unmark alert as false positive"""
    success = engine.alert_engine.unmark_false_positive(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found or not marked as false positive")
    return {"message": "Alert unmarked as false positive and removed from continuous learning"}


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Delete an alert"""
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    
    db = SessionLocal()
    try:
        alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Protect Continuous Learning: If it's a False Positive, unmark it first to remove features
        if alert.is_false_positive:
            engine.alert_engine.unmark_false_positive(alert_id)
            
        db.delete(alert)
        db.commit()
        
        return {"message": "Alert deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class BatchDeleteRequest(BaseModel):
    alert_ids: List[int]

@router.post("/batch-delete")
async def batch_delete_alerts(
    req: BatchDeleteRequest,
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Admin only: Batch delete alerts"""
    from auth import require_admin
    await require_admin(current_user)
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    
    if not req.alert_ids:
        return {"message": "No alerts to delete"}
        
    db = SessionLocal()
    try:
        # Find all FP alerts in this batch and remove their features first
        fp_alerts = db.query(AlertModel).filter(
            AlertModel.id.in_(req.alert_ids),
            AlertModel.is_false_positive == True
        ).all()
        
        for fp in fp_alerts:
            engine.alert_engine.unmark_false_positive(fp.id)
            
        # Bulk delete
        deleted_count = db.query(AlertModel).filter(AlertModel.id.in_(req.alert_ids)).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Deleted {deleted_count} alerts"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/clear-all")
async def clear_all_alerts(
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Admin only: Clear all alerts"""
    from auth import require_admin
    from db.db_manager import SessionLocal
    from db.models import AlertModel

    await require_admin(current_user)
    db = SessionLocal()
    try:
        # Find ALL FP alerts and remove their features first
        fp_alerts = db.query(AlertModel).filter(AlertModel.is_false_positive == True).all()
        for fp in fp_alerts:
            engine.alert_engine.unmark_false_positive(fp.id)
            
        # Use bulk delete without loading instances
        count = db.query(AlertModel).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully cleared {count} alerts"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/false-positives/list", response_model=List[AlertOut])
async def get_false_positive_alerts(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user),
    engine: DetectionEngine = Depends(get_engine)
):
    """Get all alerts marked as false positive"""
    from db.db_manager import SessionLocal
    from db.models import AlertModel
    
    db = SessionLocal()
    try:
        alerts = db.query(AlertModel)\
            .filter(AlertModel.is_false_positive == True)\
            .order_by(AlertModel.timestamp.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
        return [engine.alert_engine._decorate_alert_dict(alert) for alert in alerts]
    finally:
        db.close()


@router.get("/governance/rules")
async def get_governance_rules(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get all governance rules"""
    return fp_manager.get_all_rules()

@router.get("/governance/suggestions")
async def get_governance_suggestions(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get governance suggestions based on FP patterns"""
    return fp_manager.generate_governance_suggestions()

@router.get("/governance/metrics")
async def get_governance_metrics(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get FP/FN metrics comparison"""
    return fp_manager.get_metrics_comparison()

@router.put("/governance/rules/{rule_id}/toggle")
async def toggle_governance_rule(
    rule_id: str,
    is_active: bool = Query(...),
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Toggle a governance rule on/off"""
    success = fp_manager.toggle_rule(rule_id, is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule updated", "is_active": is_active}

@router.delete("/governance/rules/{rule_id}")
async def delete_governance_rule(
    rule_id: str,
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Delete a governance rule"""
    success = fp_manager.remove_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted"}

class SuggestionApply(BaseModel):
    type: str
    ip: Optional[str] = None
    port: Optional[int] = None
    feature: Optional[str] = None
    current_threshold: Optional[float] = None
    suggested_threshold: Optional[float] = None
    avg_value: Optional[float] = None
    confidence: Optional[float] = None

@router.post("/governance/apply-suggestion")
async def apply_governance_suggestion(
    suggestion: SuggestionApply,
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Apply a governance suggestion as a rule"""
    import time
    
    rule_id = f"manual_{suggestion.type}_{int(time.time())}"
    
    if suggestion.type == "whitelist_ip" and suggestion.ip:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="whitelist",
            created_at=datetime.now(),
            whitelist_ips=[suggestion.ip]
        )
    elif suggestion.type == "whitelist_port" and suggestion.port:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="whitelist",
            created_at=datetime.now(),
            whitelist_ports=[suggestion.port]
        )
    elif suggestion.type == "threshold" and suggestion.suggested_threshold:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="threshold",
            created_at=datetime.now(),
            threshold_adjustment=(suggestion.suggested_threshold - (suggestion.current_threshold or 0.5))
        )
    elif suggestion.type == "feature_rule" and suggestion.feature:
        rule = GovernanceRule(
            rule_id=rule_id,
            rule_type="feature_rule",
            created_at=datetime.now(),
            feature_name=suggestion.feature,
            feature_condition="lt",
            feature_value=suggestion.avg_value or 0
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid suggestion type or missing parameters")
    
    fp_manager.add_rule(rule)
    return {"message": "Suggestion applied", "rule_id": rule_id}

@router.get("/governance/feedback-summary")
async def get_feedback_summary(
    current_user: TokenData = Depends(get_current_user),
    fp_manager: FalsePositiveManager = Depends(get_fp_manager)
):
    """Get summary of false positive feedbacks"""
    return fp_manager.get_feedback_summary()
