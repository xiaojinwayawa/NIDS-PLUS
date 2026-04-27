<template>
  <div class="model-evaluation-container">
    <div class="header-actions">
      <h1>总体模型评估</h1>
      <div class="header-buttons">
        <el-button type="primary" @click="refreshCurrentTab">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-alert
      title="该模块为独立 CSV 回放评估空间，任务结果不会写入训练指标、实验结果或性能监控。"
      type="info"
      :closable="false"
      show-icon
      class="intro-alert"
    />

    <el-card shadow="hover">
      <template #header>
        <div class="card-header-with-tabs">
          <el-tabs v-model="activeTab" @tab-click="refreshCurrentTab">
            <el-tab-pane label="数据监测" name="monitor" />
            <el-tab-pane label="数据管理" name="management" />
          </el-tabs>
        </div>
      </template>

      <div v-if="activeTab === 'monitor'" class="monitor-tab">
        <el-row :gutter="20">
          <el-col :span="10">
            <el-card shadow="never" class="inner-card">
              <template #header>
                <span>任务配置</span>
              </template>
              <el-form :model="taskForm" label-width="110px">
                <el-form-item label="评估名称">
                  <el-input v-model="taskForm.evaluationName" placeholder="请输入本次评估名称" />
                </el-form-item>
                <el-form-item label="模型">
                  <el-select
                    v-model="taskForm.modelName"
                    placeholder="请选择 CIC-IDS2017 模型"
                    filterable
                    style="width: 100%"
                    @change="syncSelectedModel"
                  >
                    <el-option
                      v-for="model in modelOptions"
                      :key="model.name"
                      :label="`${model.name} (${model.type})`"
                      :value="model.name"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="CSV 数据">
                  <el-select
                    v-model="taskForm.sourceKeys"
                    placeholder="请选择带标签的 CSV 文件"
                    filterable
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    style="width: 100%"
                  >
                    <el-option
                      v-for="source in csvSources"
                      :key="source.sourceKey"
                      :label="`${source.display_name} [${source.dataset_type}]`"
                      :value="source.sourceKey"
                    >
                      <div class="source-option">
                        <span>{{ source.display_name }}</span>
                        <span class="source-meta">{{ source.sample_count || 0 }} 行</span>
                      </div>
                    </el-option>
                  </el-select>
                </el-form-item>
                <el-form-item label="标签列">
                  <el-input v-model="taskForm.labelColumn" placeholder="留空则自动识别 Label/label/class" />
                </el-form-item>
                <el-form-item label="批大小">
                  <el-input-number v-model="taskForm.batchSize" :min="128" :max="20000" :step="128" />
                </el-form-item>
                <el-form-item>
                  <div class="form-actions">
                    <el-button type="success" :disabled="isTaskRunning" :loading="isStarting" @click="startEvaluationTask">
                      <el-icon><VideoPlay /></el-icon>
                      开始评估
                    </el-button>
                    <el-button type="danger" plain :disabled="!isTaskRunning" @click="stopEvaluationTask">
                      <el-icon><VideoPause /></el-icon>
                      停止任务
                    </el-button>
                  </div>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="14">
            <el-card shadow="never" class="inner-card">
              <template #header>
                <span>任务进度</span>
              </template>

              <el-empty v-if="!currentTask" description="当前暂无运行中的评估任务" :image-size="90" />

              <div v-else class="task-panel">
                <div class="task-topline">
                  <el-tag :type="taskStatusType(currentTask.status)" effect="dark">
                    {{ taskStatusText(currentTask.status) }}
                  </el-tag>
                  <span class="task-name">{{ currentTask.evaluation_name }}</span>
                </div>

                <el-progress
                  :percentage="currentTask.progress || 0"
                  :status="progressStatus(currentTask.status)"
                  :stroke-width="18"
                  :text-inside="true"
                  class="task-progress"
                />

                <el-descriptions :column="2" border class="task-descriptions">
                  <el-descriptions-item label="当前阶段">{{ currentTask.stage || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="提示信息">{{ currentTask.message || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="模型">{{ currentTask.model_name || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="CSV 文件">{{ currentTask.csv_display_name || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="已处理">{{ currentTask.processed_rows || 0 }}</el-descriptions-item>
                  <el-descriptions-item label="总行数">{{ currentTask.total_rows || 0 }}</el-descriptions-item>
                </el-descriptions>

                <el-card shadow="never" class="logs-card">
                  <template #header>
                    <span>任务日志</span>
                  </template>
                  <div class="logs-panel">
                    <div v-if="!currentTask.logs || currentTask.logs.length === 0" class="no-logs">
                      暂无日志
                    </div>
                    <div v-else>
                      <div v-for="(line, index) in currentTask.logs" :key="index" class="log-line">
                        {{ line }}
                      </div>
                    </div>
                  </div>
                </el-card>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div v-else class="management-tab">
        <div class="management-toolbar">
          <el-input
            v-model="resultKeyword"
            placeholder="按评估名称或模型名称过滤"
            clearable
            style="width: 320px"
          />
          <el-button type="primary" @click="loadResults">
            <el-icon><Refresh /></el-icon>
            刷新结果
          </el-button>
        </div>

        <el-table :data="filteredResults" stripe style="width: 100%">
          <el-table-column prop="evaluation_name" label="评估名称" min-width="180" />
          <el-table-column prop="model_name" label="模型" min-width="160" />
          <el-table-column prop="csv_display_name" label="CSV 文件" min-width="200" />
          <el-table-column label="Accuracy" width="110">
            <template #default="scope">{{ formatMetric(scope.row.summary?.accuracy) }}</template>
          </el-table-column>
          <el-table-column label="F1" width="100">
            <template #default="scope">{{ formatMetric(scope.row.summary?.f1) }}</template>
          </el-table-column>
          <el-table-column label="Macro-F1" width="110">
            <template #default="scope">{{ formatMetric(scope.row.summary?.macro_f1) }}</template>
          </el-table-column>
          <el-table-column label="FPR" width="100">
            <template #default="scope">{{ formatMetric(scope.row.summary?.fpr) }}</template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="180">
            <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="290" fixed="right">
            <template #default="scope">
              <div class="table-actions">
                <el-button size="small" type="primary" @click="openResultDetail(scope.row)">详情</el-button>
                <el-button size="small" type="success" @click="exportExcel(scope.row)">导出 Excel</el-button>
                <el-button
                  v-if="systemStore.user?.role === 'admin'"
                  size="small"
                  type="danger"
                  @click="deleteResult(scope.row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-dialog
      v-model="detailDialogVisible"
      title="评估结果详情"
      width="980px"
      modal-class="app-content-dialog-mask"
    >
      <template v-if="selectedResult">
        <el-descriptions :column="2" border class="detail-descriptions">
          <el-descriptions-item label="评估名称">{{ selectedResult.evaluation_name }}</el-descriptions-item>
          <el-descriptions-item label="模型名称">{{ selectedResult.model_name }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">{{ selectedResult.model_type }}</el-descriptions-item>
          <el-descriptions-item label="CSV 文件">{{ selectedResult.csv_display_name }}</el-descriptions-item>
        </el-descriptions>

        <el-row :gutter="16" class="metric-cards">
          <el-col :span="4"><el-statistic title="Accuracy" :value="selectedResult.summary?.accuracy || 0" :precision="4" /></el-col>
          <el-col :span="4"><el-statistic title="Precision" :value="selectedResult.summary?.precision || 0" :precision="4" /></el-col>
          <el-col :span="4"><el-statistic title="Recall" :value="selectedResult.summary?.recall || 0" :precision="4" /></el-col>
          <el-col :span="4"><el-statistic title="F1" :value="selectedResult.summary?.f1 || 0" :precision="4" /></el-col>
          <el-col :span="4"><el-statistic title="Macro-F1" :value="selectedResult.summary?.macro_f1 || 0" :precision="4" /></el-col>
          <el-col :span="4"><el-statistic title="FPR" :value="selectedResult.summary?.fpr || 0" :precision="4" /></el-col>
        </el-row>

        <el-card shadow="never" class="detail-card">
          <template #header>
            <span>各类别指标</span>
          </template>
          <el-table :data="selectedResult.class_metrics || []" stripe>
            <el-table-column prop="label" label="类别" min-width="160" />
            <el-table-column prop="precision" label="Precision" width="120">
              <template #default="scope">{{ formatMetric(scope.row.precision) }}</template>
            </el-table-column>
            <el-table-column prop="recall" label="Recall" width="120">
              <template #default="scope">{{ formatMetric(scope.row.recall) }}</template>
            </el-table-column>
            <el-table-column prop="f1" label="F1" width="120">
              <template #default="scope">{{ formatMetric(scope.row.f1) }}</template>
            </el-table-column>
            <el-table-column prop="support" label="Support" width="120" />
          </el-table>
        </el-card>

        <el-card shadow="never" class="detail-card">
          <template #header>
            <span>混淆矩阵</span>
          </template>
          <el-table :data="confusionMatrixRows" stripe>
            <el-table-column prop="label" label="真实 \\ 预测" min-width="160" fixed />
            <el-table-column
              v-for="label in confusionMatrixLabels"
              :key="label"
              :label="label"
              min-width="110"
            >
              <template #default="scope">{{ scope.row[label] }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPause, VideoPlay } from '@element-plus/icons-vue'
import api from '@/api'
import { useSystemStore } from '@/stores/system'

interface EvaluationModel {
  id: number | string
  name: string
  type: string
  dataset_type?: string
  source?: string
}

interface CsvSource {
  source_kind: string
  source_value: string
  display_name: string
  dataset_type: string
  sample_count: number
  sourceKey: string
}

interface EvaluationTask {
  task_id: string
  result_id?: string
  status: string
  progress: number
  stage: string
  message: string
  processed_rows: number
  total_rows: number
  evaluation_name: string
  model_name: string
  model_type: string
  csv_display_name?: string
  logs?: string[]
}

const ACTIVE_TASK_KEY = 'modelEvaluationActiveTaskId'

const systemStore = useSystemStore()
const activeTab = ref<'monitor' | 'management'>('monitor')
const models = ref<EvaluationModel[]>([])
const csvSources = ref<CsvSource[]>([])
const results = ref<any[]>([])
const currentTask = ref<EvaluationTask | null>(null)
const pollTimer = ref<number | null>(null)
const isStarting = ref(false)
const resultKeyword = ref('')
const detailDialogVisible = ref(false)
const selectedResult = ref<any | null>(null)

const taskForm = reactive({
  evaluationName: '',
  modelName: '',
  modelType: '',
  datasetType: '',
  sourceKeys: [] as string[],
  labelColumn: '',
  batchSize: 2048
})

const modelOptions = computed(() => models.value)

const filteredResults = computed(() => {
  const keyword = resultKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return results.value
  }
  return results.value.filter(item =>
    `${item.evaluation_name} ${item.model_name} ${item.csv_display_name}`.toLowerCase().includes(keyword)
  )
})

const isTaskRunning = computed(() =>
  isStarting.value || (currentTask.value != null && ['pending', 'running'].includes(currentTask.value.status))
)

const confusionMatrixLabels = computed(() => selectedResult.value?.confusion_matrix?.labels || [])

const confusionMatrixRows = computed(() => {
  if (!selectedResult.value?.confusion_matrix) {
    return []
  }
  const labels = selectedResult.value.confusion_matrix.labels || []
  const matrix = selectedResult.value.confusion_matrix.matrix || []
  return labels.map((label: string, rowIndex: number) => {
    const row: Record<string, string | number> = { label }
    labels.forEach((columnLabel: string, colIndex: number) => {
      row[columnLabel] = matrix[rowIndex]?.[colIndex] ?? 0
    })
    return row
  })
})

const formatMetric = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '-'
  }
  return Number(value).toFixed(4)
}

const formatTime = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const taskStatusText = (status: string) => {
  const mapping: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止'
  }
  return mapping[status] || status
}

const taskStatusType = (status: string) => {
  const mapping: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    stopped: 'info'
  }
  return mapping[status] || 'info'
}

const progressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return undefined
}

const syncSelectedModel = () => {
  const selected = modelOptions.value.find(model => model.name === taskForm.modelName)
  taskForm.modelType = selected?.type || ''
  taskForm.datasetType = selected?.dataset_type || ''
}

const loadModels = async () => {
  const res = await api.get('/models/')
  models.value = res.data
  if (!taskForm.modelName && modelOptions.value.length > 0) {
    taskForm.modelName = modelOptions.value[0].name
    syncSelectedModel()
  }
}

const loadSources = async () => {
  const res = await api.get('/model-evaluation/sources')
  csvSources.value = (res.data.sources || []).map((item: any) => ({
    ...item,
    sourceKey: `${item.source_kind}:${item.source_value}`
  }))
  if (taskForm.sourceKeys.length === 0 && csvSources.value.length > 0) {
    taskForm.sourceKeys = [csvSources.value[0].sourceKey]
  }
}

const loadResults = async () => {
  const res = await api.get('/model-evaluation/results')
  results.value = res.data.results || []
}

const refreshCurrentTab = async () => {
  if (activeTab.value === 'monitor') {
    await Promise.all([loadModels(), loadSources()])
    if (currentTask.value?.task_id) {
      await pollTask(currentTask.value.task_id)
    }
  } else {
    await loadResults()
  }
}

const startPollingTask = (taskId: string) => {
  stopPollingTask()
  localStorage.setItem(ACTIVE_TASK_KEY, taskId)
  pollTimer.value = window.setInterval(() => {
    pollTask(taskId)
  }, 2000)
}

const stopPollingTask = () => {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const pollTask = async (taskId: string) => {
  try {
    const res = await api.get(`/model-evaluation/tasks/${taskId}`)
    currentTask.value = res.data
    if (!['pending', 'running'].includes(res.data.status)) {
      stopPollingTask()
      localStorage.removeItem(ACTIVE_TASK_KEY)
      await loadResults()
      if (res.data.status === 'completed') {
        ElMessage.success('总体模型评估任务已完成')
      } else if (res.data.status === 'failed') {
        ElMessage.error(res.data.message || '总体模型评估任务失败')
      }
    }
  } catch (error: any) {
    stopPollingTask()
    localStorage.removeItem(ACTIVE_TASK_KEY)
    currentTask.value = null
    ElMessage.error(error.response?.data?.detail || '获取评估任务进度失败')
  }
}

const startEvaluationTask = async () => {
  if (isStarting.value) return
  if (!taskForm.evaluationName.trim()) {
    ElMessage.warning('请输入评估名称')
    return
  }
  if (!taskForm.modelName || taskForm.sourceKeys.length === 0) {
    ElMessage.warning('请选择模型和至少一个 CSV 文件')
    return
  }
  syncSelectedModel()

  const payload = {
    evaluation_name: taskForm.evaluationName.trim(),
    model_name: taskForm.modelName,
    model_type: taskForm.modelType,
    dataset_type: taskForm.datasetType,
    source_keys: taskForm.sourceKeys,
    label_column: taskForm.labelColumn.trim() || null,
    batch_size: taskForm.batchSize
  }

  try {
    isStarting.value = true
    const res = await api.post('/model-evaluation/tasks', payload)
    currentTask.value = res.data.task
    ElMessage.success('总体模型评估任务已启动')
    startPollingTask(res.data.task.task_id)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动评估任务失败')
  } finally {
    isStarting.value = false
  }
}

const stopEvaluationTask = async () => {
  if (!currentTask.value) return
  try {
    await api.post(`/model-evaluation/tasks/${currentTask.value.task_id}/stop`)
    ElMessage.success('已请求停止当前评估任务')
    await pollTask(currentTask.value.task_id)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '停止评估任务失败')
  }
}

const openResultDetail = async (row: any) => {
  try {
    const res = await api.get(`/model-evaluation/results/${row.result_id}`)
    selectedResult.value = res.data
    detailDialogVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载评估结果详情失败')
  }
}

const exportExcel = async (row: any) => {
  try {
    const res = await api.get(`/model-evaluation/results/${row.result_id}/export/excel`, {
      responseType: 'blob'
    })
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${row.evaluation_name || 'model_evaluation'}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('Excel 导出成功')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Excel 导出失败')
  }
}

const deleteResult = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除评估结果“${row.evaluation_name}”吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.delete(`/model-evaluation/results/${row.result_id}`)
    ElMessage.success('评估结果已删除')
    await loadResults()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除评估结果失败')
    }
  }
}

onMounted(async () => {
  await Promise.all([loadModels(), loadSources(), loadResults()])
  const activeTaskId = localStorage.getItem(ACTIVE_TASK_KEY)
  if (activeTaskId) {
    await pollTask(activeTaskId)
    if (currentTask.value && ['pending', 'running'].includes(currentTask.value.status)) {
      startPollingTask(activeTaskId)
    }
  }
})

onUnmounted(() => {
  stopPollingTask()
})
</script>

<style scoped>
.model-evaluation-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions h1 {
  margin: 0;
  font-size: 22px;
  color: #303133;
}

.intro-alert {
  margin-bottom: 4px;
}

.card-header-with-tabs {
  display: flex;
  align-items: center;
}

.card-header-with-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.monitor-tab,
.management-tab {
  min-height: 420px;
}

.inner-card {
  min-height: 420px;
}

.form-actions,
.table-actions,
.header-buttons {
  display: flex;
  gap: 10px;
}

.source-option {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.source-meta {
  color: #909399;
  margin-left: 12px;
}

.task-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-topline {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-name {
  font-weight: 600;
  color: #303133;
}

.task-progress {
  margin-top: 8px;
}

.task-descriptions {
  margin-top: 8px;
}

.logs-card {
  margin-top: 6px;
}

.logs-panel {
  max-height: 220px;
  overflow: auto;
  background: #0f172a;
  color: #dbeafe;
  padding: 12px;
  border-radius: 6px;
  font-family: Consolas, monospace;
  font-size: 12px;
}

.log-line + .log-line {
  margin-top: 6px;
}

.no-logs {
  color: #94a3b8;
}

.management-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.detail-descriptions,
.detail-card {
  margin-bottom: 18px;
}

.metric-cards {
  margin: 18px 0;
}
</style>
