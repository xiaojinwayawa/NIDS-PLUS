<template>
  <div class="training-container">
    <div class="header-actions">
      <h1>Model Training & Management</h1>
      <el-button type="primary" @click="refresh">Refresh</el-button>
    </div>

    <el-card class="form-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>Train New Model</span>
        </div>
      </template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="Model Type">
          <el-select v-model="form.model_type" placeholder="Select type" style="width: 240px" :disabled="training">
            <el-option label="LightGBM" value="lightgbm" />
            <el-option label="XGBoost" value="xgboost" />
          </el-select>
        </el-form-item>
        <el-form-item label="Model Name">
          <el-input v-model="form.model_name" placeholder="Optional (auto-generated if empty)" :disabled="training" />
        </el-form-item>
        <el-form-item label="Dataset">
          <el-select v-model="form.dataset_id" placeholder="Select dataset" style="width: 320px" @change="onDatasetChange" :disabled="training">
            <el-option
              v-for="d in datasets"
              :key="d.id"
              :label="`${d.name} (${d.type})`"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button :loading="training" type="success" @click="startTraining">
            {{ training ? 'Training...' : 'Start Training' }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- Training Progress -->
      <div v-if="training || trainProgress" class="training-progress">
        <div class="progress-header">
          <span class="progress-stage">{{ trainProgress?.message || 'Initializing...' }}</span>
          <span class="progress-time">{{ formatTime(trainProgress?.elapsed || 0) }}</span>
        </div>
        <el-progress 
          :percentage="trainProgress?.percent || 0" 
          :status="progressStatus"
          :stroke-width="20"
          :text-inside="true"
        />
        <div class="progress-stage-info">
          Stage: {{ trainProgress?.stage || 'initializing' }}
        </div>
      </div>
      
      <!-- Training Result -->
      <div v-if="trainResult && !training" class="train-result">
        <el-alert type="success" :title="`Training completed: Model ID ${trainResult.model_id}`" show-icon />
        <el-descriptions :column="2" border style="margin-top: 10px">
          <el-descriptions-item label="Accuracy">{{ trainResult.metrics?.accuracy?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="Precision">{{ trainResult.metrics?.precision?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="Recall">{{ trainResult.metrics?.recall?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="F1">{{ trainResult.metrics?.f1?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="Training Time">{{ trainResult.metrics?.training_time?.toFixed(2) }}s</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <el-card class="list-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>Models</span>
        </div>
      </template>
      <el-table :data="models" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Name" width="200" />
        <el-table-column prop="type" label="Type" width="140" />
        <el-table-column prop="version" label="Version" width="100" />
        <el-table-column label="Metrics" min-width="220">
          <template #default="scope">
            <div v-if="scope.row.metrics">
              Acc: {{ scope.row.metrics.accuracy?.toFixed(3) }},
              F1: {{ scope.row.metrics.f1?.toFixed(3) }}
            </div>
            <div v-else>—</div>
          </template>
        </el-table-column>
        <el-table-column prop="dataset_type" label="Dataset" width="160" />
        <el-table-column prop="is_active" label="Active" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'">
              {{ scope.row.is_active ? 'Active' : 'Inactive' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" type="primary" :disabled="scope.row.is_active" @click="activate(scope.row)">Activate</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

interface DatasetInfo {
  id: number
  name: string
  type: string
  sample_count?: number
  source?: string
  file_path?: string
}

interface TrainingProgress {
  stage: string
  current: number
  total: number
  percent: number
  message: string
  elapsed: number
  model_id?: number
  metrics?: any
}

const datasets = ref<DatasetInfo[]>([])
const models = ref<any[]>([])
const training = ref(false)
const trainResult = ref<any>(null)
const trainProgress = ref<TrainingProgress | null>(null)
const selectedDataset = ref<DatasetInfo | null>(null)
const currentTaskId = ref<string | null>(null)
let progressInterval: number | null = null

const form = ref({
  model_type: 'lightgbm',
  model_name: '',
  dataset_id: null as number | null
})

const progressStatus = computed(() => {
  if (!trainProgress.value) return ''
  if (trainProgress.value.stage === 'error') return 'exception'
  if (trainProgress.value.stage === 'complete') return 'success'
  return ''
})

const formatTime = (seconds: number) => {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(0)
  return `${mins}m ${secs}s`
}

const loadDatasets = async () => {
  const res = await api.get('/datasets/')
  datasets.value = res.data
}

const loadModels = async () => {
  const res = await api.get('/models/')
  models.value = res.data
}

const onDatasetChange = (datasetId: number) => {
  selectedDataset.value = datasets.value.find(d => d.id === datasetId) || null
}

const pollProgress = async () => {
  if (!currentTaskId.value) return
  
  try {
    const res = await api.get(`/models/train/progress/${currentTaskId.value}`)
    trainProgress.value = res.data
    
    if (res.data.stage === 'complete') {
      // Training completed
      training.value = false
      trainResult.value = {
        model_id: res.data.model_id,
        metrics: res.data.metrics
      }
      stopPolling()
      ElMessage.success('Training completed!')
      await loadModels()
    } else if (res.data.stage === 'error') {
      // Training failed
      training.value = false
      stopPolling()
      ElMessage.error(res.data.message || 'Training failed')
    }
  } catch (e) {
    // Ignore polling errors
  }
}

const startPolling = () => {
  if (progressInterval) return
  progressInterval = window.setInterval(pollProgress, 500)
}

const stopPolling = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

const startTraining = async () => {
  if (!form.value.dataset_id) {
    ElMessage.warning('Please select dataset')
    return
  }
  
  training.value = true
  trainResult.value = null
  trainProgress.value = null
  
  try {
    const payload: any = {
      model_type: form.value.model_type,
      dataset_id: form.value.dataset_id,
      model_name: form.value.model_name || undefined
    }
    
    // For preset datasets (negative ID), also send file_path
    if (selectedDataset.value && selectedDataset.value.id < 0 && selectedDataset.value.file_path) {
      payload.dataset_path = selectedDataset.value.file_path
    }
    
    const res = await api.post('/models/train', payload)
    currentTaskId.value = res.data.task_id
    
    // Start polling for progress
    startPolling()
    
  } catch (e: any) {
    training.value = false
    ElMessage.error(e.response?.data?.detail || 'Training failed')
  }
}

const activate = async (model: any) => {
  try {
    // For preset models (negative ID), send model_name and model_type as query params
    if (model.id < 0) {
      await api.post(`/models/activate/${model.id}?model_name=${model.name}&model_type=${model.type}`)
    } else {
      await api.post(`/models/activate/${model.id}`)
    }
    
    ElMessage.success('Model activated')
    await loadModels()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Activation failed')
  }
}

const refresh = async () => {
  await loadDatasets()
  await loadModels()
}

onMounted(() => {
  refresh()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.training-container {
  padding-bottom: 20px;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.form-card, .list-card {
  margin-bottom: 20px;
}
.training-progress {
  margin-top: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.progress-stage {
  font-weight: 500;
  color: #409eff;
}
.progress-time {
  color: #909399;
  font-size: 14px;
}
.progress-stage-info {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  text-transform: capitalize;
}
.train-result {
  margin-top: 20px;
}
</style>
