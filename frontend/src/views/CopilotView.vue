<template>
  <div class="copilot-container">
    <el-card class="chat-card">
      <template #header>
        <div class="card-header">
          <div class="title-with-icon">
            <el-icon class="sparkle-icon"><Star /></el-icon>
            <span>NIDS-Copilot 智能安全助手</span>
          </div>
        </div>
      </template>

      <!-- Chat History -->
      <div class="chat-history" ref="chatHistoryRef">
        <div v-for="(msg, index) in chatMessages" :key="index" 
             :class="['chat-bubble-wrapper', msg.role === 'user' ? 'user-wrapper' : 'assistant-wrapper']">
          
          <el-avatar v-if="msg.role === 'assistant'" :size="36" class="assistant-avatar">
            <el-icon><Monitor /></el-icon>
          </el-avatar>
          
          <div :class="['chat-bubble', msg.role === 'user' ? 'user-bubble' : 'assistant-bubble']">
            <div v-if="msg.role === 'assistant' && msg.content" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
            <div v-else-if="msg.role === 'user'">{{ msg.content }}</div>
            
            <div v-if="msg.isLoading" class="loading-dots">
              <span>.</span><span>.</span><span>.</span>
            </div>
          </div>
          
          <el-avatar v-if="msg.role === 'user'" :size="36" class="user-avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="quick-actions" v-if="chatMessages.length === 1">
        <el-button round size="small" @click="sendQuickMessage('系统现在的运行状态如何？')">📊 系统状态</el-button>
        <el-button round size="small" @click="sendQuickMessage('帮我分析一下最近的攻击告警')">🛡️ 告警分析</el-button>
        <el-button round size="small" @click="sendQuickMessage('如何使用总体模型评估功能？')">📈 模型评估</el-button>
        <el-button round size="small" @click="sendQuickMessage('如何使用类别平衡器？')">📖 操作指南</el-button>
      </div>

      <!-- Input Area -->
      <div class="chat-input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="3"
          placeholder="问我关于系统操作、告警分析的任何问题... (Enter 发送, Shift+Enter 换行)"
          @keydown.enter.prevent="handleEnter"
          :disabled="isSending"
        />
        <div class="input-actions">
          <span class="hint">按 Enter 发送</span>
          <el-button type="primary" :icon="Position" @click="sendMessage" :loading="isSending" :disabled="!inputText.trim()">发送</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { Star, Monitor, User, Position } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import api from '@/api'

const chatHistoryRef = ref(null)
const inputText = ref('')
const isSending = ref(false)

// Init message
const chatMessages = ref([
  { 
    role: 'assistant', 
    content: '你好！我是 NIDS-Copilot，你的专属安全运营智能助手。\n\n我可以帮你：\n- 📝 **解答操作问题**：如“如何训练模型”、“如何开启实时检测”\n- 🔍 **研判安全态势**：如“帮我分析最近的告警”\n\n请问有什么我可以帮您的？',
    isLoading: false
  }
])

const renderMarkdown = (text) => {
  if (!text) return ''
  return marked(text)
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatHistoryRef.value) {
    chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
  }
}

const handleEnter = (e) => {
  if (!e.shiftKey) {
    sendMessage()
  }
}

const sendQuickMessage = (text) => {
  inputText.value = text
  sendMessage()
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isSending.value) return
  
  // Add user message
  chatMessages.value.push({ role: 'user', content: text })
  inputText.value = ''
  isSending.value = true
  scrollToBottom()

  // Add loading bubble
  chatMessages.value.push({ role: 'assistant', content: '', isLoading: true })
  scrollToBottom()

  try {
    // Format messages for API (excluding loading indicators)
    const apiMessages = chatMessages.value
      .filter(m => !m.isLoading && m.content)
      .map(m => ({ role: m.role, content: m.content }))

    const response = await api.post('/copilot/chat', {
      messages: apiMessages
    })

    // Remove loading bubble
    chatMessages.value.pop()
    
    // Add real response
    if (response.data && response.data.message) {
      chatMessages.value.push({
        role: 'assistant',
        content: response.data.message.content,
        isLoading: false
      })
    }
  } catch (error) {
    console.error('Copilot error:', error)
    chatMessages.value.pop() // remove loading
    chatMessages.value.push({
      role: 'assistant',
      content: '⚠️ 抱歉，连接 AI 助手失败，请检查后端 API 密钥配置及网络状态。',
      isLoading: false
    })
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.copilot-container {
  padding: 20px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.chat-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
  font-size: 16px;
}

.sparkle-icon {
  color: #e6a23c;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.7; }
  100% { transform: scale(1); opacity: 1; }
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: #f5f7fa;
}

.chat-bubble-wrapper {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

.user-wrapper {
  justify-content: flex-end;
}

.assistant-wrapper {
  justify-content: flex-start;
}

.assistant-avatar {
  background-color: #409EFF;
  margin-right: 12px;
}

.user-avatar {
  background-color: #67C23A;
  margin-left: 12px;
}

.chat-bubble {
  max-width: 90%;
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.5;
  font-size: 14px;
  word-wrap: break-word;
}

.user-bubble {
  background-color: #e1f3d8;
  color: #333;
  border-bottom-right-radius: 2px;
}

.assistant-bubble {
  background-color: #fff;
  color: #333;
  border-bottom-left-radius: 2px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  border: 1px solid transparent;
  transition: all 0.3s;
}

.assistant-bubble:hover {
  border-color: #c6e2ff;
  box-shadow: 0 0 8px rgba(64,158,255,0.2);
}

.quick-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  padding: 10px;
  background-color: #f5f7fa;
}

.chat-input-area {
  padding: 15px 20px;
  background-color: #fff;
  border-top: 1px solid #ebeef5;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.hint {
  font-size: 12px;
  color: #909399;
}

.loading-dots span {
  animation: dots 1.4s infinite ease-in-out both;
  font-size: 20px;
  line-height: 10px;
}
.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes dots {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

/* Markdown Styles */
:deep(.markdown-body) {
  font-size: 14px;
}
:deep(.markdown-body ul), :deep(.markdown-body ol) {
  padding-left: 20px;
  margin-top: 4px;
  margin-bottom: 4px;
}
:deep(.markdown-body p:last-child) {
  margin-bottom: 0;
}
:deep(.markdown-body pre) {
  background-color: #f6f8fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}
:deep(.markdown-body code) {
  background-color: #f6f8fa;
  padding: 2px 4px;
  border-radius: 3px;
}
</style>
