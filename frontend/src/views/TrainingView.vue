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
          <el-select v-model="form.model_type" placeholder="Select type" style="width: 240px">
            <el-option label="LightGBM" value="lightgbm" />
            <el-option label="XGBoost" value="xgboost" />
          </el-select>
        </el-form-item>
        <el-form-item label="Model Name">
          <el-input v-model="form.model_name" placeholder="Optional (auto-generated if empty)" />
        </el-form-item>
        <el-form-item label="Dataset">
          <el-select v-model="form.dataset_id" placeholder="Select dataset" style="width: 320px">
            <el-option
              v-for="d in datasets"
              :key="d.id"
              :label="`${d.name} (${d.type})`"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button :loading="training" type="success" @click="startTraining">Start Training</el-button>
        </el-form-item>
      </el-form>
      <div v-if="trainResult" class="train-result">
        <el-alert type="success" :title="`Training completed: ${trainResult.model_id}`" show-icon />
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Accuracy">{{ trainResult.metrics?.accuracy?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="Precision">{{ trainResult.metrics?.precision?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="Recall">{{ trainResult.metrics?.recall?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="F1">{{ trainResult.metrics?.f1?.toFixed(4) }}</el-descriptions-item>
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
            <el-button size="small" type="primary" :disabled="scope.row.is_active" @click="activate(scope.row.id)">Activate</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

const datasets = ref<Array<{id:number; name:string; type:string}>>([])
const models = ref<any[]>([])
const training = ref(false)
const trainResult = ref<any>(null)

const form = ref({
  model_type: 'lightgbm',
  model_name: '',
  dataset_id: null as number | null
})

const loadDatasets = async () => {
  const res = await api.get('/datasets/')
  datasets.value = res.data
}

const loadModels = async () => {
  const res = await api.get('/models/')
  models.value = res.data
}

const startTraining = async () => {
  if (!form.value.dataset_id) {
    ElMessage.warning('Please select dataset')
    return
  }
  training.value = true
  try {
    const res = await api.post('/models/train', {
      model_type: form.value.model_type,
      dataset_id: form.value.dataset_id,
      model_name: form.value.model_name || undefined
    })
    trainResult.value = res.data
    ElMessage.success('Training completed')
    await loadModels()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Training failed')
  } finally {
    training.value = false
  }
}

const activate = async (id: number) => {
  try {
    await api.post(`/models/activate/${id}`)
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
.train-result {
  margin-top: 20px;
}
</style>
