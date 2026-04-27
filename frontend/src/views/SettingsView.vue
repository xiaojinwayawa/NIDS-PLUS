<template>
  <div class="settings-container">
    <div class="header-actions">
      <h1>系统设置</h1>
      <el-button type="primary" @click="loadConfig">刷新</el-button>
    </div>

    <el-card shadow="hover" class="settings-card">
      <template #header><span>全局配置</span></template>
      <el-form :model="config" label-width="160px">
        <el-form-item label="告警阈值">
          <el-input-number v-model="config.alert_threshold" :min="0" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="批次大小">
          <el-input-number v-model="config.batch_size" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item label="启用SHAP">
          <el-switch v-model="config.enable_shap" />
        </el-form-item>
        <el-form-item label="日志级别">
          <el-select v-model="config.log_level" style="width: 200px">
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="saving" @click="saveConfig">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover" class="settings-card">
      <template #header><span>模型融合策略</span></template>
      <el-form :model="fusionConfig" label-width="160px">
        <el-form-item label="融合策略">
          <el-select v-model="fusionConfig.strategy" style="width: 200px">
            <el-option label="投票（多数）" value="voting" />
            <el-option label="加权平均" value="weighted" />
            <el-option label="级联（ML→DL）" value="cascade" />
          </el-select>
          <div class="strategy-hint">
            <span v-if="fusionConfig.strategy === 'voting'">硬投票：多数模型决定</span>
            <span v-else-if="fusionConfig.strategy === 'weighted'">模型概率的加权平均</span>
            <span v-else-if="fusionConfig.strategy === 'cascade'">先使用ML，不确定的情况使用DL</span>
          </div>
        </el-form-item>
        <el-form-item v-if="fusionConfig.strategy === 'cascade'" label="级联阈值">
          <el-slider v-model="fusionConfig.cascade_threshold" :min="0.5" :max="0.9" :step="0.05" show-input style="width: 300px" />
          <div class="strategy-hint">置信度低于此值的样本使用DL模型</div>
        </el-form-item>
        <el-form-item v-if="fusionConfig.strategy === 'weighted'" label="模型权重">
          <div class="weight-inputs">
            <div v-for="(weight, model) in fusionConfig.weights" :key="model" class="weight-item">
              <span class="weight-label">{{ model }}:</span>
              <el-input-number v-model="fusionConfig.weights[model]" :min="0" :max="10" :step="0.1" size="small" />
            </div>
            <el-button size="small" type="primary" text @click="addWeightModel">+ 添加模型</el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="savingFusion" @click="saveFusionConfig">保存融合配置</el-button>
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
  alert_threshold: 0.5,
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
    ElMessage.error(e.response?.data?.detail || '加载配置失败')
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
    console.log('使用默认融合配置')
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    await api.put('/system/config', config.value)
    ElMessage.success('配置已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新配置失败')
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
    ElMessage.success('融合配置已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新融合配置失败')
  } finally {
    savingFusion.value = false
  }
}

const addWeightModel = async () => {
  const { value } = await ElMessageBox.prompt('输入模型名称：', '添加模型权重', {
    confirmButtonText: '添加',
    cancelButtonText: '取消'
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
.settings-container {
  padding-bottom: 24px;
}

.settings-card {
  margin-bottom: 24px;
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

.settings-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.settings-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.settings-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
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
