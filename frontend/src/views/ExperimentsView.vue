<template>
  <div class="experiments-container">
    <div class="header-actions">
      <h1>Experiments</h1>
      <div class="actions">
        <el-button type="primary" @click="showNewExperiment = true">New Experiment</el-button>
        <el-button type="success" @click="showCompare = true">Run Comparison</el-button>
        <el-button @click="loadExperiments">Refresh</el-button>
      </div>
    </div>
    <el-card shadow="hover" class="list-card">
      <template #header><span>Experiment Results</span></template>
      <el-table :data="experiments" style="width: 100%" stripe>
        <el-table-column prop="name" label="Name" min-width="180" />
        <el-table-column prop="dataset_type" label="Dataset" width="120" />
        <el-table-column label="Models" min-width="160">
          <template #default="scope">
            <el-tag v-for="m in scope.row.model_types" :key="m" size="small" style="margin-right: 4px">{{ m }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="accuracy" label="Accuracy" width="100">
          <template #default="scope">{{ scope.row.accuracy?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column prop="f1_score" label="F1" width="80">
          <template #default="scope">{{ scope.row.f1_score?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="scope">
            <el-button size="small" type="primary" @click="viewDetail(scope.row)">Detail</el-button>
            <el-button size="small" type="danger" @click="deleteExp(scope.row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="showNewExperiment" title="New Experiment" width="500px">
      <el-form :model="newExpForm" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="newExpForm.experiment_name" />
        </el-form-item>
        <el-form-item label="Dataset">
          <el-select v-model="newExpForm.dataset_type" style="width: 100%">
            <el-option label="NSL-KDD" value="nsl-kdd" />
            <el-option label="CIC-IDS2017" value="cic-ids2017" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewExperiment = false">Cancel</el-button>
        <el-button type="primary" @click="runExp">Run</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showCompare" title="Run Comparison" width="400px">
      <el-form label-width="100px">
        <el-form-item label="Dataset">
          <el-select v-model="compareDataset" style="width: 100%">
            <el-option label="NSL-KDD" value="nsl-kdd" />
            <el-option label="CIC-IDS2017" value="cic-ids2017" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCompare = false">Cancel</el-button>
        <el-button type="success" @click="runCompare">Run</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const experiments = ref<any[]>([])
const showNewExperiment = ref(false)
const showCompare = ref(false)
const compareDataset = ref('nsl-kdd')
const newExpForm = ref({
  experiment_name: '',
  dataset_type: 'nsl-kdd',
  model_types: ['lightgbm', 'xgboost'],
  fusion_strategy: 'weighted',
  dl_epochs: 50
})

const loadExperiments = async () => {
  try {
    const res = await api.get('/experiments/')
    experiments.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to load')
  }
}

const viewDetail = async (row: any) => {
  try {
    const res = await api.get(`/experiments/${row.experiment_id}`)
    ElMessageBox.alert(JSON.stringify(res.data.metrics, null, 2), 'Detail')
  } catch (e: any) {
    ElMessage.error('Failed to load detail')
  }
}

const deleteExp = async (row: any) => {
  try {
    await ElMessageBox.confirm('Delete this experiment?', 'Confirm')
    await api.delete(`/experiments/${row.experiment_id}`)
    ElMessage.success('Deleted')
    await loadExperiments()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('Failed to delete')
  }
}

const runExp = async () => {
  if (!newExpForm.value.experiment_name) {
    ElMessage.warning('Please enter name')
    return
  }
  try {
    await api.post('/experiments/run', newExpForm.value)
    ElMessage.success('Experiment started')
    showNewExperiment.value = false
  } catch (e: any) {
    ElMessage.error('Failed to start')
  }
}

const runCompare = async () => {
  try {
    await api.post('/experiments/compare', { dataset_type: compareDataset.value })
    ElMessage.success('Comparison started')
    showCompare.value = false
  } catch (e: any) {
    ElMessage.error('Failed to start')
  }
}

onMounted(() => loadExperiments())
</script>

<style scoped>
.experiments-container { padding-bottom: 20px; }
.header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.actions { display: flex; gap: 10px; }
.list-card { margin-bottom: 20px; }
</style>
