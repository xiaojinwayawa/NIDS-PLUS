<template>
  <div class="training-container">
    <!-- Training Lock Overlay -->
    <div v-if="training" class="training-overlay">
      <el-card class="training-modal">
        <h2>Training in Progress</h2>
        <div class="progress-info">
          <p class="progress-message">{{ trainProgress?.message || 'Initializing...' }}</p>
          <el-progress :percentage="trainProgress?.percent || 0" :stroke-width="20" :text-inside="true" />
          <p class="progress-time">Elapsed: {{ formatTime(trainProgress?.elapsed || 0) }}</p>
        </div>
        <el-button type="danger" size="large" @click="stopTraining">Stop Training</el-button>
        <p class="warning-text">Stopping will delete the incomplete model</p>
      </el-card>
    </div>

    <div class="header-actions">
      <h1>Model Training & Management</h1>
      <div class="action-buttons">
        <el-button type="primary" @click="loadData" :loading="loading">Load Data</el-button>
        <el-button @click="refresh">Refresh</el-button>
      </div>
    </div>

    <el-card class="form-card" shadow="hover">
      <template #header><span>Train New Model</span></template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="Model Type">
          <el-cascader
            v-model="form.model_type_path"
            :options="modelTypeOptions"
            :props="{ expandTrigger: 'click' }"
            placeholder="Select model type"
            style="width: 280px"
            @change="onModelTypeChange"
          />
        </el-form-item>
        <el-form-item v-if="isDLModel" label="Epochs">
          <el-input-number v-model="form.epochs" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="Model Name">
          <el-input v-model="form.model_name" placeholder="Optional (auto-generated if empty)" />
        </el-form-item>
        <el-form-item label="Datasets">
          <el-select
            v-model="form.dataset_ids"
            multiple
            filterable
            placeholder="Select one or more datasets"
            style="width: 320px"
            @change="onDatasetChange"
          >
            <el-option v-for="d in datasets" :key="d.id" :label="`${d.name} (${d.type})`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="success" @click="startTraining" :disabled="form.dataset_ids.length === 0">
            Start Training ({{ form.dataset_ids.length }})
          </el-button>
        </el-form-item>
      </el-form>
      
      <div v-if="trainResult" class="train-result">
        <el-alert type="success" :title="`Training completed: Model ID ${trainResult.model_id}`" show-icon />
        <el-descriptions :column="2" border style="margin-top: 10px">
          <el-descriptions-item label="Accuracy">{{ trainResult.metrics?.accuracy?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="F1">{{ trainResult.metrics?.f1?.toFixed(4) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <el-card class="list-card" shadow="hover">
      <template #header><span>Models</span></template>
      <el-table :data="models" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Name" width="200" />
        <el-table-column prop="type" label="Type" width="140" />
        <el-table-column label="Metrics" min-width="200">
          <template #default="scope">
            <span v-if="scope.row.metrics">Acc: {{ scope.row.metrics.accuracy?.toFixed(3) }}, F1: {{ scope.row.metrics.f1?.toFixed(3) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="dataset_type" label="Dataset" width="140" />
        <el-table-column prop="is_active" label="Active" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'">{{ scope.row.is_active ? 'Active' : 'Inactive' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" type="primary" :disabled="scope.row.is_active" @click="activate(scope.row)">Activate</el-button>
            <el-button size="small" type="danger" :disabled="scope.row.is_active" @click="deleteModel(scope.row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

interface DatasetInfo { id: number; name: string; type: string; file_path?: string }
interface TrainingProgress { stage: string; percent: number; message: string; elapsed: number; model_id?: number; metrics?: any }

const datasets = ref<DatasetInfo[]>([])
const models = ref<any[]>([])
const training = ref(false)
const loading = ref(false)
const trainResult = ref<any>(null)
const trainProgress = ref<TrainingProgress | null>(null)
const selectedDatasets = ref<DatasetInfo[]>([])
const currentTaskId = ref<string | null>(null)
let progressInterval: number | null = null

const form = ref({ model_type: 'lightgbm', model_type_path: ['ml', 'lightgbm'] as string[], model_name: '', dataset_ids: [] as number[], epochs: 20 })
const isDLModel = computed(() => ['cnn', 'gru', 'transformer'].includes(form.value.model_type))
const formatTime = (s: number) => s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s/60)}m ${(s%60).toFixed(0)}s`

// Model type cascader options
const modelTypeOptions = [
  {
    value: 'ml',
    label: '🤖 Traditional ML',
    children: [
      { value: 'lightgbm', label: '⚡ LightGBM' },
      { value: 'xgboost', label: '🚀 XGBoost' }
    ]
  },
  {
    value: 'dl',
    label: '🧠 Deep Learning',
    children: [
      { value: 'cnn', label: '📊 1D-CNN' },
      { value: 'gru', label: '🔄 GRU' },
      { value: 'transformer', label: '🔮 Transformer' }
    ]
  }
]

const onModelTypeChange = (value: string[]) => {
  if (value && value.length === 2) {
    form.value.model_type = value[1]
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const [dsRes, mdRes] = await Promise.all([api.get('/datasets/'), api.get('/models/')])
    datasets.value = dsRes.data
    models.value = mdRes.data
    ElMessage.success('Data loaded')
  } catch (e: any) {
    ElMessage.error('Failed to load data')
  } finally {
    loading.value = false
  }
}

const refresh = () => loadData()
const onDatasetChange = (ids: number[]) => {
  selectedDatasets.value = datasets.value.filter(d => ids.includes(d.id))
}

const pollProgress = async () => {
  if (!currentTaskId.value) return
  try {
    const res = await api.get(`/models/train/progress/${currentTaskId.value}`)
    trainProgress.value = res.data
    if (res.data.stage === 'complete') {
      training.value = false
      trainResult.value = { model_id: res.data.model_id, metrics: res.data.metrics }
      stopPolling()
      ElMessage.success('Training completed!')
      await loadData()
    } else if (res.data.stage === 'error') {
      training.value = false
      stopPolling()
      ElMessage.error(res.data.message || 'Training failed')
    } else if (res.data.stage === 'stopped') {
      training.value = false
      stopPolling()
      ElMessage.info('Training stopped')
    }
  } catch (e) {
    // Task not found - training was stopped or completed
    training.value = false
    stopPolling()
  }
}

const startPolling = () => { if (!progressInterval) progressInterval = window.setInterval(pollProgress, 500) }
const stopPolling = () => { if (progressInterval) { clearInterval(progressInterval); progressInterval = null } }

const startTraining = async () => {
  if (form.value.dataset_ids.length === 0) { ElMessage.warning('Please select at least one dataset'); return }
  training.value = true
  trainResult.value = null
  trainProgress.value = null
  try {
    const payload: any = {
      model_type: form.value.model_type,
      dataset_ids: form.value.dataset_ids,
      model_name: form.value.model_name || undefined
    }
    const datasetPaths = selectedDatasets.value.map(d => d.file_path).filter(Boolean) as string[]
    if (datasetPaths.length > 0) payload.dataset_paths = datasetPaths
    if (isDLModel.value) payload.epochs = form.value.epochs
    const res = await api.post('/models/train', payload)
    currentTaskId.value = res.data.task_id
    startPolling()
  } catch (e: any) {
    training.value = false
    ElMessage.error(e.response?.data?.detail || 'Training failed')
  }
}

const stopTraining = async () => {
  // 先关闭训练遮罩层，让确认框可见
  training.value = false
  
  try {
    await ElMessageBox.confirm('Stop training and delete incomplete model?', 'Confirm', {
      confirmButtonText: 'Stop',
      cancelButtonText: 'Continue Training',
      type: 'warning'
    })
    // 用户确认停止
    if (currentTaskId.value) {
      try { await api.post(`/models/train/stop/${currentTaskId.value}`) } catch (e) {}
    }
    trainProgress.value = null
    currentTaskId.value = null
    stopPolling()
    ElMessage.info('Training stopped')
  } catch (e) {
    // 用户点击取消，恢复训练遮罩层
    training.value = true
  }
}

const activate = async (model: any) => {
  try {
    if (model.id < 0) await api.post(`/models/activate/${model.id}?model_name=${model.name}&model_type=${model.type}`)
    else await api.post(`/models/activate/${model.id}`)
    ElMessage.success('Model activated')
    await loadData()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || 'Activation failed') }
}

const deleteModel = async (model: any) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete model "${model.name}"? This action cannot be undone.`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )
    
    await api.delete(`/models/${model.id}`)
    ElMessage.success('Model deleted successfully')
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || 'Delete failed')
    }
  }
}

onMounted(() => loadData())
onUnmounted(() => stopPolling())
</script>

<style scoped>
.training-container { padding-bottom: 20px; position: relative; }
.header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.action-buttons { display: flex; gap: 10px; }
.form-card, .list-card { margin-bottom: 20px; }
.train-result { margin-top: 20px; }
.training-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 9999; display: flex; align-items: center; justify-content: center; }
.training-modal { width: 400px; text-align: center; padding: 30px; }
.training-modal h2 { margin-bottom: 20px; color: #409eff; }
.progress-info { margin: 20px 0; }
.progress-message { font-size: 16px; margin-bottom: 15px; color: #606266; }
.progress-time { margin-top: 10px; color: #909399; }
.warning-text { margin-top: 15px; font-size: 12px; color: #f56c6c; }
</style>