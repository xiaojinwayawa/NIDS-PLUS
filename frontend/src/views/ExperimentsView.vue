<template>
  <div class="experiments-container">
    <!-- 实验运行锁定遮罩层 -->
    <div v-if="runningTask" class="experiment-overlay">
      <el-card class="experiment-modal">
        <h2>实验运行中</h2>
        <div class="progress-info">
          <p class="progress-message">{{ runningTask.message || '初始化中...' }}</p>
          <el-progress 
            :percentage="runningTask.progress" 
            :status="runningTask.status === 'failed' ? 'exception' : (runningTask.status === 'completed' ? 'success' : '')"
            :stroke-width="20" 
            :text-inside="true" 
          />
        </div>
        <p class="warning-text">请勿关闭浏览器，您可以切换到其他模块，实验将在后台继续运行。</p>
      </el-card>
    </div>

    <div class="header-actions">
      <h1>实验</h1>
      <div class="actions">
        <el-button type="primary" @click="showNewExperiment = true">自定义实验</el-button>
        <el-button @click="loadExperiments">刷新</el-button>
      </div>
    </div>

    <el-card shadow="hover" class="list-card">
      <template #header><span>实验结果</span></template>
      <el-table :data="experiments" style="width: 100%" stripe>
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="dataset_type" label="数据集" width="120" />
        <el-table-column label="模型" min-width="160">
          <template #default="scope">
            <el-tag v-for="m in scope.row.model_types" :key="m" size="small" style="margin-right: 4px">{{ m }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="产出模型" min-width="180">
          <template #default="scope">
            <div v-for="m in scope.row.experiment_models || []" :key="m.name || m.type" style="margin-bottom: 6px">
              <el-tag
                size="small"
                style="margin-right: 6px"
                :title="m.name || m.display_name"
              >
                {{ m.type }}
              </el-tag>
              <el-tag size="small" :type="m.promoted ? 'success' : 'info'" style="margin-right: 6px">
                {{ m.promoted ? '已转正式' : '实验模型' }}
              </el-tag>
              <el-button
                size="small"
                link
                type="primary"
                :disabled="m.promoted"
                @click="promoteModel(scope.row, m)"
              >
                {{ m.promoted ? '已转正式' : '转正式' }}
              </el-button>
            </div>
            <span v-if="!scope.row.experiment_models || scope.row.experiment_models.length === 0">-</span>
          </template>
        </el-table-column>
        <el-table-column label="融合结果" min-width="160">
          <template #default="scope">
            <span v-if="scope.row.fusion_result">
              {{ formatStrategy(scope.row.fusion_result.strategy) }} / F1: {{ scope.row.fusion_result.metrics?.f1?.toFixed(4) ?? '-' }}
            </span>
            <span v-else>无</span>
          </template>
        </el-table-column>
        <el-table-column prop="accuracy" label="Accuracy" width="100">
          <template #default="scope">{{ scope.row.accuracy?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column prop="f1_score" label="F1" width="80">
          <template #default="scope">{{ scope.row.f1_score?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="scope">
            <el-button size="small" type="primary" @click="viewDetail(scope.row)">详情</el-button>
            <el-button size="small" type="danger" @click="deleteExp(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="showNewExperiment" title="新建实验" width="600px" modal-class="app-content-dialog-mask">
      <el-form :model="newExpForm" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="newExpForm.experiment_name" placeholder="输入实验名称" />
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="newExpForm.dataset_type" style="width: 100%" @change="onDatasetChange">
            <el-option label="NSL-KDD" value="nsl-kdd" />
            <el-option label="CIC-IDS2017" value="cic-ids2017" />
          </el-select>
        </el-form-item>
        
        <!-- CIC-IDS2017 文件选择 -->
        <el-form-item label="CIC-IDS2017文件" v-if="newExpForm.dataset_type === 'cic-ids2017'">
          <div style="max-height: 300px; overflow-y: auto; border: 1px solid #dcdfe6; border-radius: 4px;">
            <el-checkbox-group v-model="newExpForm.cicids2017_files">
              <div v-for="file in cicids2017Files" :key="file.filename" style="padding: 8px 12px; border-bottom: 1px solid #f0f0f0; cursor: pointer;">
                <el-checkbox :value="file.filename">
                  {{ file.filename }} ({{ file.estimated_rows.toLocaleString() }} 行)
                </el-checkbox>
              </div>
            </el-checkbox-group>
          </div>
        </el-form-item>
        
        <el-form-item label="模型">
          <el-checkbox-group v-model="newExpForm.model_types">
            <el-checkbox label="lightgbm">LightGBM</el-checkbox>
            <el-checkbox label="xgboost">XGBoost</el-checkbox>
            <el-checkbox label="cnn">1D-CNN</el-checkbox>
            <el-checkbox label="gru">GRU</el-checkbox>
            <el-checkbox label="transformer">Transformer</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="误报回流注入">
          <el-switch 
            v-model="newExpForm.use_human_feedback" 
            active-text="开启 (Human-in-the-Loop)" 
            inactive-text="关闭"
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.4;">
            开启后，系统会自动将人工标记的误报特征数据(FP)回流并注入到当前训练集中，进行过采样以增强第一级拦截模型的抗误报能力。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewExperiment = false">取消</el-button>
        <el-button type="primary" @click="runExp">运行</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showDetailDialog" title="实验详情" width="760px" modal-class="app-content-dialog-mask">
      <template v-if="selectedExperimentDetail">
        <el-card shadow="never" class="detail-section">
          <template #header><span>实验信息</span></template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="实验名称">{{ selectedExperimentDetail.config?.experiment_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="数据集">{{ selectedExperimentDetail.config?.dataset_type || '-' }}</el-descriptions-item>
            <el-descriptions-item label="模型组合">{{ (selectedExperimentDetail.config?.model_types || []).join(', ') || '-' }}</el-descriptions-item>
            <el-descriptions-item label="融合策略">
              {{ selectedExperimentDetail.fusion_result ? formatStrategy(selectedExperimentDetail.fusion_result.strategy) : '无' }}
            </el-descriptions-item>
            <el-descriptions-item label="最终 Accuracy">{{ formatMetric(selectedExperimentDetail.metrics?.accuracy) }}</el-descriptions-item>
            <el-descriptions-item label="最终 F1">{{ formatMetric(selectedExperimentDetail.metrics?.f1_score) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="detail-section">
          <template #header><span>单模型产物</span></template>
          <el-table :data="selectedExperimentDetail.experiment_models || []" stripe>
            <el-table-column prop="type" label="模型类型" width="120" />
            <el-table-column prop="name" label="实验模型名" min-width="220" />
            <el-table-column label="状态" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.promoted ? 'success' : 'info'">
                  {{ scope.row.promoted ? '已转正式' : '实验模型' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="正式模型" min-width="180">
              <template #default="scope">
                <span>{{ scope.row.promoted_model_name || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="detail-section">
          <template #header><span>融合结果</span></template>
          <template v-if="selectedExperimentDetail.fusion_result">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="结果名称">融合结果</el-descriptions-item>
              <el-descriptions-item label="融合策略">{{ formatStrategy(selectedExperimentDetail.fusion_result.strategy) }}</el-descriptions-item>
              <el-descriptions-item label="来源模型">
                {{ (selectedExperimentDetail.fusion_result.source_models || []).join(', ') || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="Accuracy">{{ formatMetric(selectedExperimentDetail.fusion_result.metrics?.accuracy) }}</el-descriptions-item>
              <el-descriptions-item label="Precision">{{ formatMetric(selectedExperimentDetail.fusion_result.metrics?.precision) }}</el-descriptions-item>
              <el-descriptions-item label="Recall">{{ formatMetric(selectedExperimentDetail.fusion_result.metrics?.recall) }}</el-descriptions-item>
              <el-descriptions-item label="F1">{{ formatMetric(selectedExperimentDetail.fusion_result.metrics?.f1) }}</el-descriptions-item>
              <el-descriptions-item label="FPR">{{ formatMetric(selectedExperimentDetail.fusion_result.metrics?.fpr) }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="当前实验只有单模型结果，没有融合结果" :image-size="80" />
        </el-card>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const experiments = ref<any[]>([])
const showNewExperiment = ref(false)
const showDetailDialog = ref(false)
const cicids2017Files = ref<any[]>([])
const selectedExperimentDetail = ref<any | null>(null)
const newExpForm = ref({
  experiment_name: '',
  dataset_type: 'nsl-kdd',
  model_types: ['lightgbm', 'xgboost'],
  fusion_strategy: 'weighted',
  dl_epochs: 50,
  cicids2017_files: [] as string[],
  use_human_feedback: true
})

const runningTask = ref<{ id: string, status: string, progress: number, message: string } | null>(null)
let taskPollInterval: number | null = null
const EXPERIMENT_TASK_KEY = 'experimentTaskId'

const saveExperimentTaskId = (taskId: string | null) => {
  if (taskId) {
    sessionStorage.setItem(EXPERIMENT_TASK_KEY, taskId)
  } else {
    sessionStorage.removeItem(EXPERIMENT_TASK_KEY)
  }
}

const loadCICIDS2017Files = async () => {
  try {
    const res = await api.get('/experiments/datasets/cicids2017/files')
    cicids2017Files.value = res.data.files || []
  } catch (e: any) {
    console.error('Failed to load CIC-IDS2017 files:', e)
  }
}

const onDatasetChange = () => {
  // Reset file selection when dataset changes
  if (newExpForm.value.dataset_type === 'cic-ids2017') {
    loadCICIDS2017Files()
  }
}



const formatMetric = (value: number | undefined | null) =>
  typeof value === 'number' ? value.toFixed(4) : '-'

const formatStrategy = (strategy: string | undefined) => {
  const strategyMap: Record<string, string> = {
    voting: '投票融合',
    weighted: '加权融合',
    cascade: '级联融合'
  }
  return strategy ? (strategyMap[strategy] || strategy) : '-'
}

const loadExperiments = async () => {
  try {
    const res = await api.get('/experiments/')
    experiments.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  }
}

const viewDetail = async (row: any) => {
  try {
    const res = await api.get(`/experiments/${row.experiment_id}`)
    selectedExperimentDetail.value = res.data
    showDetailDialog.value = true
  } catch (e: any) {
    ElMessage.error('加载详情失败')
  }
}

const deleteExp = async (row: any) => {
  try {
    await ElMessageBox.confirm('删除此实验吗？', '确认')
    await api.delete(`/experiments/${row.experiment_id}`)
    ElMessage.success('已删除')
    await loadExperiments()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const promoteModel = async (row: any, model: any) => {
  try {
    const defaultName = `${row.name || 'experiment'}_${model.type}`
    const promptRes = await ElMessageBox.prompt('请输入正式模型名称', '转正式模型', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: defaultName,
      inputPattern: /^[A-Za-z0-9_-]+$/,
      inputErrorMessage: '只允许字母、数字、下划线和短横线'
    })

    await api.post(`/experiments/${row.experiment_id}/promote`, {
      model_type: model.type,
      model_name: promptRes.value
    })
    ElMessage.success('已转为正式模型')
    await loadExperiments()
    if (selectedExperimentDetail.value?.experiment_id === row.experiment_id) {
      await viewDetail(row)
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '转正式模型失败')
    }
  }
}

const runExp = async () => {
  if (!newExpForm.value.experiment_name) {
    ElMessage.warning('请输入名称')
    return
  }
  
  // Validate CIC-IDS2017 file selection
  if (newExpForm.value.dataset_type === 'cic-ids2017') {
    if (!newExpForm.value.cicids2017_files || newExpForm.value.cicids2017_files.length === 0) {
      ElMessage.warning('请至少选择一个CIC-IDS2017文件')
      return
    }
  }

  if (newExpForm.value.model_types.length === 0) {
    ElMessage.warning('请至少选择一个模型')
    return
  }
  
  try {
    const res = await api.post('/experiments/run', newExpForm.value)
    ElMessage.success('实验已开始')
    showNewExperiment.value = false
    
    // Start polling progress
    if (res.data && res.data.task_id) {
      runningTask.value = {
        id: res.data.task_id,
        status: 'running',
        progress: 0,
        message: '正在初始化...'
      }
      saveExperimentTaskId(res.data.task_id)
      startPollingTask()
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '启动实验失败')
  }
}

const startPollingTask = () => {
  if (taskPollInterval) clearInterval(taskPollInterval)
  
  taskPollInterval = window.setInterval(async () => {
    if (!runningTask.value) {
      if (taskPollInterval) clearInterval(taskPollInterval)
      return
    }
    
    try {
      const res = await api.get(`/experiments/task/${runningTask.value.id}`)
      const data = res.data
      
      runningTask.value = {
        id: data.task_id || runningTask.value.id,
        status: data.status,
        progress: data.progress,
        message: data.message
      }
      
      if (data.status === 'completed' || data.status === 'failed') {
        if (taskPollInterval) clearInterval(taskPollInterval)
        taskPollInterval = null
        saveExperimentTaskId(null)
        
        if (data.status === 'completed') {
          ElMessage.success('实验完成！')
          await loadExperiments()
        } else {
          ElMessage.error(`实验失败: ${data.message}`)
        }
        
        // Hide progress bar after a delay
        setTimeout(() => {
          runningTask.value = null
        }, 2000)
      }
    } catch (e) {
      console.error('Error polling task status', e)
    }
  }, 1000)
}

const restoreExperimentTask = async () => {
  const savedTaskId = sessionStorage.getItem(EXPERIMENT_TASK_KEY)
  if (savedTaskId) {
    try {
      const res = await api.get(`/experiments/task/${savedTaskId}`)
      const data = res.data
      if (data.status === 'running') {
        runningTask.value = {
          id: savedTaskId,
          status: data.status,
          progress: data.progress,
          message: data.message
        }
        startPollingTask()
      } else {
        saveExperimentTaskId(null)
        loadExperiments()
      }
    } catch (e) {
      saveExperimentTaskId(null)
    }
  }
}

// 离开路由时的提示
onBeforeRouteLeave((to, from, next) => {
  if (runningTask.value && runningTask.value.status === 'running') {
    ElMessageBox.confirm(
      '当前有正在进行的实验任务，离开页面不会中断后台运行，下次返回时将恢复进度显示。确定要离开吗？',
      '实验运行中',
      {
        confirmButtonText: '离开',
        cancelButtonText: '留在本页',
        type: 'warning'
      }
    ).then(() => {
      next()
    }).catch(() => {
      next(false)
    })
  } else {
    next()
  }
})

onUnmounted(() => {
  if (taskPollInterval) {
    clearInterval(taskPollInterval)
  }
})

onMounted(() => {
  loadExperiments()
  restoreExperimentTask()
})
</script>

<style scoped>
.experiments-container {
  padding-bottom: 24px;
}

.experiment-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.9);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
  backdrop-filter: blur(2px);
}

.experiment-modal {
  width: 500px;
  text-align: center;
  padding: 20px;
}

.experiment-modal h2 {
  margin-top: 0;
  margin-bottom: 24px;
  color: var(--el-text-color-primary);
}

.progress-info {
  margin: 30px 0;
}

.progress-message {
  margin-bottom: 15px;
  color: var(--el-text-color-regular);
  font-size: 15px;
}

.warning-text {
  margin-top: 24px;
  color: var(--el-color-warning);
  font-size: 13px;
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

.actions {
  display: flex;
  gap: 12px;
}

.experiments-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.experiments-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.experiments-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.experiments-container :deep(.el-table) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
}

.experiments-container :deep(.el-table th) {
  background: #fafafa;
  color: #606266;
  font-weight: 500;
}

.experiments-container :deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafafa;
}

.progress-card {
  border-radius: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.list-card {
  margin-bottom: 24px;
  border-radius: 8px;
}

.detail-section {
  margin-bottom: 16px;
}
</style>
