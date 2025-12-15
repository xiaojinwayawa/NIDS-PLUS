<template>
  <div class="settings-container">
    <div class="header-actions">
      <h1>System Settings</h1>
      <el-button type="primary" @click="loadConfig">Refresh</el-button>
    </div>

    <el-card shadow="hover">
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
  </div>
 </template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

const config = ref({
  alert_threshold: 0.8,
  batch_size: 100,
  enable_shap: true,
  log_level: 'INFO'
})
const saving = ref(false)

const loadConfig = async () => {
  const res = await api.get('/system/config')
  config.value = res.data
}

const saveConfig = async () => {
  saving.value = true
  try {
    const res = await api.put('/system/config', config.value)
    ElMessage.success('Configuration updated')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to update config')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.settings-container { padding-bottom: 20px; }
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style>
