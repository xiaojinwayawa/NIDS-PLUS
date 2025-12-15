<template>
  <div class="logs-container">
    <div class="header-actions">
      <h1>System Logs</h1>
      <el-select v-model="lines" style="width: 160px" @change="fetchContent">
        <el-option label="Last 100 lines" :value="100" />
        <el-option label="Last 500 lines" :value="500" />
        <el-option label="Last 1000 lines" :value="1000" />
      </el-select>
    </div>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><span>Files</span></template>
          <el-table :data="files" style="width: 100%" height="500" @row-click="selectFile">
            <el-table-column prop="name" label="Filename" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header><span>Content: {{ currentFile || '—' }}</span></template>
          <pre class="log-content">{{ content }}</pre>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

const files = ref<Array<{name:string}>>([])
const currentFile = ref<string | null>(null)
const content = ref('')
const lines = ref(100)

const loadFiles = async () => {
  try {
    const res = await api.get('/logs/')
    files.value = res.data.map((n:string) => ({ name: n }))
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to load log files')
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
    ElMessage.error(e.response?.data?.detail || 'Failed to load log content')
  }
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
.logs-container { padding-bottom: 20px; }
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.log-content {
  height: 500px;
  overflow-y: auto;
  background: #0f0f0f;
  color: #e8e8e8;
  font-family: Consolas, monospace;
  padding: 12px;
  white-space: pre-wrap;
}
</style>
