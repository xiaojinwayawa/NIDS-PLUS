<template>
  <div class="logs-container">
    <div class="header-actions">
      <h1>系统日志</h1>
      <div class="controls">
        <el-select v-model="lines" style="width: 160px" @change="fetchContent">
          <el-option label="最近100行" :value="100" />
          <el-option label="最近500行" :value="500" />
          <el-option label="最近1000行" :value="1000" />
        </el-select>
        <el-button @click="loadFiles">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><span>文件</span></template>
          <el-table :data="files" style="width: 100%" height="500" @row-click="selectFile">
            <el-table-column prop="name" label="文件名" />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="scope">
                <el-button 
                  size="small" 
                  type="danger" 
                  text 
                  @click.stop="deleteLogFile(scope.row.name)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="content-header">
              <span>内容: {{ currentFile || '—' }}</span>
              <el-button 
                v-if="currentFile"
                size="small" 
                type="danger" 
                text 
                @click="deleteLogFile(currentFile)"
              >
                删除当前文件
              </el-button>
            </div>
          </template>
          <pre class="log-content">{{ content }}</pre>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const files = ref<Array<{name:string}>>([])
const currentFile = ref<string | null>(null)
const content = ref('')
const lines = ref(100)

const loadFiles = async () => {
  try {
    const res = await api.get('/logs/')
    files.value = res.data.map((n:string) => ({ name: n }))
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载日志文件失败')
  }
}

const selectFile = (row: any) => {
  currentFile.value = row.name
  fetchContent()
}

const fetchContent = async () => {
  if (!currentFile.value) return
  try {
    const res = await api.get(`/logs/${currentFile.value}`, { params: { lines: lines.value } })
    content.value = (res.data.content || []).join('')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载日志内容失败')
  }
}

const deleteLogFile = async (filename: string) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除日志文件 "${filename}" 吗？此操作不可撤销。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await api.delete(`/logs/${filename}`)
    ElMessage.success('日志文件删除成功')
    
    // 如果删除的是当前文件，清空内容
    if (currentFile.value === filename) {
      currentFile.value = null
      content.value = ''
    }
    
    // 重新加载文件列表
    await loadFiles()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除日志文件失败')
    }
  }
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
.logs-container {
  padding-bottom: 24px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-actions h1 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logs-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.logs-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.logs-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.logs-container :deep(.el-table) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
}

.logs-container :deep(.el-table th) {
  background: #fafafa;
  color: #606266;
  font-weight: 500;
}

.log-content {
  height: 500px;
  overflow-y: auto;
  background: #1f1f1f;
  color: #e8e8e8;
  font-family: Consolas, monospace;
  padding: 16px;
  white-space: pre-wrap;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
}
</style>
