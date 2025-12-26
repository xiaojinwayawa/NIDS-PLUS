<template>
  <div class="settings-container">
    <div class="header-actions">
      <h1>System Settings</h1>
      <el-button type="primary" @click="loadConfig">Refresh</el-button>
    </div>

    <el-card shadow="hover" class="settings-card">
      <template #header><span>Global Configuration</span></template>
      <el-form :model="config" label-width="160px">
        <el-form-item label="Alert Threshold">
          <el-input-number v-model="config.alert_threshold" :min="0" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="Batch Size">
          <el-input-number v-model="config.batch_size" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item label="Enable SHAP">
          <el-switch v-model="config.enable_shap" />
        </el-form-item>
        <el-form-item label="Log Level">
          <el-select v-model="config.log_level" style="width: 200px">
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="saving" @click="saveConfig">Save</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover" class="settings-card">
      <template #header><span>Model Fusion Strategy</span></template>
      <el-form :model="fusionConfig" label-width="160px">
        <el-form-item label="Fusion Strategy">
          <el-select v-model="fusionConfig.strategy" style="width: 200px">
            <el-option label="Voting (Majority)" value="voting" />
            <el-option label="Weighted Average" value="weighted" />
            <el-option label="Cascade (ML→DL)" value="cascade" />
          </el-select>
          <div class="strategy-hint">
            <span v-if="fusionConfig.strategy === 'voting'">Hard voting: majority of models decide</span>
            <span v-else-if="fusionConfig.strategy === 'weighted'">Weighted average of model probabilities</span>
            <span v-else-if="fusionConfig.strategy === 'cascade'">ML first, DL for uncertain cases</span>
          </div>
        </el-form-item>
        <el-form-item v-if="fusionConfig.strategy === 'cascade'" label="Cascade Threshold">
          <el-slider v-model="fusionConfig.cascade_threshold" :min="0.5" :max="0.9" :step="0.05" show-input style="width: 300px" />
          <div class="strategy-hint">Samples with confidence below this use DL model</div>
        </el-form-item>
        <el-form-item v-if="fusionConfig.strategy === 'weighted'" label="Model Weights">
          <div class="weight-inputs">
            <div v-for="(weight, model) in fusionConfig.weights" :key="model" class="weight-item">
              <span class="weight-label">{{ model }}:</span>
              <el-input-number v-model="fusionConfig.weights[model]" :min="0" :max="10" :step="0.1" size="small" />
            </div>
            <el-button size="small" type="primary" text @click="addWeightModel">+ Add Model</el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="savingFusion" @click="saveFusionConfig">Save Fusion Config</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
 </template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const config = ref({
  alert_threshold: 0.8,
  batch_size: 100,
  enable_shap: true,
  log_level: 'INFO'
})

const fusionConfig = ref({
  strategy: 'weighted',
  cascade_threshold: 0.7,
  weights: {} as Record<string, number>
})

const saving = ref(false)
const savingFusion = ref(false)

const loadConfig = async () => {
  try {
    const res = await api.get('/system/config')
    config.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to load config')
  }
}

const loadFusionConfig = async () => {
  try {
    const res = await api.get('/system/fusion-config')
    fusionConfig.value = {
      strategy: res.data.fusion_strategy || 'weighted',
      cascade_threshold: res.data.cascade_threshold || 0.7,
      weights: res.data.model_weights || {}
    }
  } catch (e: any) {
    // Use defaults if not configured
    console.log('Using default fusion config')
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    await api.put('/system/config', config.value)
    ElMessage.success('Configuration updated')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to update config')
  } finally {
    saving.value = false
  }
}

const saveFusionConfig = async () => {
  savingFusion.value = true
  try {
    await api.put('/system/fusion-config', {
      strategy: fusionConfig.value.strategy,
      cascade_threshold: fusionConfig.value.cascade_threshold,
      weights: fusionConfig.value.weights
    })
    ElMessage.success('Fusion configuration updated')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to update fusion config')
  } finally {
    savingFusion.value = false
  }
}

const addWeightModel = async () => {
  const { value } = await ElMessageBox.prompt('Enter model name:', 'Add Model Weight', {
    confirmButtonText: 'Add',
    cancelButtonText: 'Cancel'
  })
  if (value) {
    fusionConfig.value.weights[value] = 1.0
  }
}

onMounted(() => {
  loadConfig()
  loadFusionConfig()
})
</script>

<style scoped>
.settings-container { padding-bottom: 20px; }
.settings-card { margin-bottom: 20px; }
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.strategy-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.weight-inputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.weight-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.weight-label {
  min-width: 100px;
  font-weight: 500;
}
</style>
