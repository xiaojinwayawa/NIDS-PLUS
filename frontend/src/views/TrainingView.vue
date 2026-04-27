<template>
  <div class="training-container">
    <!-- 训练锁定遮罩层 -->
    <div v-if="training" class="training-overlay">
      <el-card class="training-modal">
        <h2>训练进行中</h2>
        <div class="progress-info">
          <p class="progress-message">{{ trainProgress?.message || '初始化中...' }}</p>
          <el-progress :percentage="trainProgress?.percent || 0" :stroke-width="20" :text-inside="true" />
          <p class="progress-time">已用时: {{ formatTime(trainProgress?.elapsed || 0) }}</p>
        </div>
        <el-button type="danger" size="large" @click="stopTraining">停止训练</el-button>
        <p class="warning-text">停止将删除未完成的模型</p>
      </el-card>
    </div>

    <div class="header-actions">
      <h1>模型训练与管理</h1>
      <div class="action-buttons">
        <el-button type="primary" @click="loadData" :loading="loading">加载数据</el-button>
        <el-button @click="refresh">刷新</el-button>
      </div>
    </div>

    <el-card class="form-card" shadow="hover">
      <template #header><span>训练新模型</span></template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="模型类型">
          <el-cascader
            v-model="form.model_type_path"
            :options="modelTypeOptions"
            :props="{ expandTrigger: 'click' }"
            placeholder="选择模型类型"
            style="width: 280px"
            @change="onModelTypeChange"
          />
        </el-form-item>
        <el-form-item v-if="isDLModel" label="训练轮次">
          <el-input-number v-model="form.epochs" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model_name" placeholder="可选（留空将自动生成）" />
        </el-form-item>
        <el-form-item label="数据集">
          <el-select
            v-model="form.dataset_ids"
            multiple
            filterable
            placeholder="选择一个或多个数据集"
            style="width: 320px"
            @change="onDatasetChange"
          >
            <el-option v-for="d in datasets" :key="d.id" :label="`${d.name} (${d.type})`" :value="d.id" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="不平衡处理 (SMOTE)">
          <el-switch v-model="form.use_smote" active-text="开启" inactive-text="关闭" />
          <span style="margin-left: 10px; font-size: 12px; color: #909399;">(提示：使用外部平衡后的数据时请保持关闭)</span>
        </el-form-item>

        <el-form-item>
          <el-button type="success" @click="startTraining" :disabled="form.dataset_ids.length === 0">
            开始训练 ({{ form.dataset_ids.length }})
          </el-button>
          <el-button type="warning" plain @click="balancerVisible = true" style="margin-left: 15px;">
            ⚖️ 类别平衡器 (Data Balancer)
          </el-button>
        </el-form-item>
      </el-form>
      
      <div v-if="trainResult" class="train-result">
        <el-alert type="success" :title="`训练完成: 模型ID ${trainResult.model_id}`" show-icon />
        <el-descriptions :column="2" border style="margin-top: 10px">
          <el-descriptions-item label="准确率">{{ trainResult.metrics?.accuracy?.toFixed(4) }}</el-descriptions-item>
          <el-descriptions-item label="F1值">{{ trainResult.metrics?.f1?.toFixed(4) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <el-card class="list-card" shadow="hover">
      <template #header><span>模型列表</span></template>
      <el-table :data="models" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="type" label="类型" width="140" />
        <el-table-column label="指标" min-width="200">
          <template #default="scope">
            <span v-if="scope.row.metrics">准确率: {{ scope.row.metrics.accuracy?.toFixed(3) }}, F1: {{ scope.row.metrics.f1?.toFixed(3) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="dataset_type" label="数据集" width="140" />

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" type="danger" @click="deleteModel(scope.row)" v-if="systemStore.user?.role === 'admin'">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 独立类别平衡器 (Data Balancer) -->
    <el-dialog v-model="balancerVisible" title="⚖️ 类别平衡器 (Data Balancer)" width="600px" :close-on-click-modal="false" @close="stopBalancerPolling">
      <el-alert
        title="严格时序平衡：保留小类的原始交互顺序（大类截断，小类循环复制）"
        type="warning"
        :closable="false"
        style="margin-bottom: 20px"
      />
      <el-form label-width="120px" :disabled="balancing">
        <el-form-item label="源数据集" required>
          <el-select v-model="balancerForm.dataset_ids" multiple placeholder="可多选，合并平衡" style="width: 100%">
            <el-option v-for="d in datasets" :key="d.id" :label="`${d.name} (${d.type})`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="新文件命名" required>
          <el-input v-model="balancerForm.output_name" placeholder="如: balanced_friday" />
        </el-form-item>
        <el-form-item label="单类上限 (大类)">
          <el-input-number v-model="balancerForm.max_samples" :min="10000" :step="10000" style="width: 160px" />
        </el-form-item>
        <el-form-item label="单类下限 (小类)">
          <el-input-number v-model="balancerForm.min_samples" :min="1000" :step="1000" style="width: 160px" />
        </el-form-item>
      </el-form>

      <div v-if="balancerProgress" style="margin-top: 20px;">
        <p>{{ balancerProgress.message }} ({{ formatTime(balancerProgress.elapsed) }})</p>
        <el-progress :percentage="balancerProgress.percent" :status="balancerProgress.stage === 'complete' ? 'success' : (balancerProgress.stage === 'error' ? 'exception' : '')" />
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="balancerVisible = false" :disabled="balancing">取消</el-button>
          <el-button type="primary" @click="startBalancing" :loading="balancing">开始平衡</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSystemStore } from '@/stores/system'

const systemStore = useSystemStore()

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
const TRAINING_TASK_KEY = 'trainingTaskId'

const form = ref({ model_type: 'lightgbm', model_type_path: ['ml', 'lightgbm'] as string[], model_name: '', dataset_ids: [] as number[], epochs: 20, use_smote: false })
const isDLModel = computed(() => ['cnn', 'cnn_resattn', 'gru', 'transformer'].includes(form.value.model_type))

// Balancer state
const balancerVisible = ref(false)
const balancing = ref(false)
const balancerForm = ref({ dataset_ids: [] as number[], output_name: '', max_samples: 100000, min_samples: 10000 })
const balancerProgress = ref<any>(null)
let balancerInterval: number | null = null
let currentBalanceTaskId: string | null = null
const formatTime = (s: number) => s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s/60)}m ${(s%60).toFixed(0)}s`

// 模型类型级联选择器选项
const modelTypeOptions = [
  {
    value: 'ml',
    label: '🤖 传统机器学习',
    children: [
      { value: 'lightgbm', label: '⚡ LightGBM' },
      { value: 'xgboost', label: '🚀 XGBoost' }
    ]
  },
  {
    value: 'dl',
    label: '🧠 深度学习',
    children: [
      { value: 'cnn', label: '📊 1D-CNN' },
      { value: 'cnn_resattn', label: '📈 1D-CNN（残差&注意力）' },
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
    console.log('开始加载数据...')
    const [dsRes, mdRes] = await Promise.all([api.get('/datasets/'), api.get('/models/')])
    console.log('数据集API返回:', dsRes)
    console.log('模型API返回:', mdRes)
    datasets.value = dsRes.data
    models.value = mdRes.data
    console.log('datasets赋值:', datasets.value)
    console.log('models赋值:', models.value)
    ElMessage.success('数据加载成功')
  } catch (e: any) {
    console.error('加载数据失败，详细错误:', e)
    console.error('错误响应:', e.response?.data)
    console.error('错误消息:', e.message)
    ElMessage.error('加载数据失败: ' + (e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const refresh = () => loadData()
const onDatasetChange = (ids: number[]) => {
  selectedDatasets.value = datasets.value.filter(d => ids.includes(d.id))
}

const saveTrainingTaskId = (taskId: string | null) => {
  if (taskId) {
    sessionStorage.setItem(TRAINING_TASK_KEY, taskId)
  } else {
    sessionStorage.removeItem(TRAINING_TASK_KEY)
  }
}

const pollProgress = async () => {
  if (!currentTaskId.value) return
  try {
    const res = await api.get(`/models/train/progress/${currentTaskId.value}`)
    trainProgress.value = res.data
    if (res.data.stage === 'complete') {
      training.value = false
      trainResult.value = { model_id: res.data.model_id, metrics: res.data.metrics }
      saveTrainingTaskId(null)
      currentTaskId.value = null
      stopPolling()
      ElMessage.success('训练完成！')
      await loadData()
    } else if (res.data.stage === 'error') {
      training.value = false
      saveTrainingTaskId(null)
      currentTaskId.value = null
      stopPolling()
      ElMessage.error(res.data.message || '训练失败')
    } else if (res.data.stage === 'stopped') {
      training.value = false
      saveTrainingTaskId(null)
      currentTaskId.value = null
      stopPolling()
      ElMessage.info('训练已停止')
    } else {
      training.value = true
    }
  } catch (e) {
    // Task not found - training was stopped or completed
    training.value = false
    saveTrainingTaskId(null)
    currentTaskId.value = null
    stopPolling()
  }
}

const startPolling = () => { if (!progressInterval) progressInterval = window.setInterval(pollProgress, 500) }
const stopPolling = () => { if (progressInterval) { clearInterval(progressInterval); progressInterval = null } }

const restoreTrainingTask = async () => {
  if (currentTaskId.value) return

  const savedTaskId = sessionStorage.getItem(TRAINING_TASK_KEY)
  if (!savedTaskId) return

  currentTaskId.value = savedTaskId
  try {
    const res = await api.get(`/models/train/progress/${savedTaskId}`)
    trainProgress.value = res.data

    if (['complete', 'error', 'stopped'].includes(res.data.stage)) {
      training.value = false
      if (res.data.stage === 'complete') {
        trainResult.value = { model_id: res.data.model_id, metrics: res.data.metrics }
      }
      saveTrainingTaskId(null)
      currentTaskId.value = null
      return
    }

    training.value = true
    startPolling()
  } catch (e) {
    training.value = false
    currentTaskId.value = null
    saveTrainingTaskId(null)
  }
}

const startTraining = async () => {
  if (form.value.dataset_ids.length === 0) { ElMessage.warning('请至少选择一个数据集'); return }
  training.value = true
  trainResult.value = null
  trainProgress.value = null
  try {
    const payload: any = {
      model_type: form.value.model_type,
      dataset_ids: form.value.dataset_ids,
      model_name: form.value.model_name || undefined,
      epochs: isDLModel.value ? form.value.epochs : undefined,
      use_smote: form.value.use_smote
    }
    const datasetPaths = selectedDatasets.value.map(d => d.file_path).filter(Boolean) as string[]
    if (datasetPaths.length > 0) payload.dataset_paths = datasetPaths
    const res = await api.post('/models/train', payload)
    currentTaskId.value = res.data.task_id
    saveTrainingTaskId(currentTaskId.value)
    startPolling()
  } catch (e: any) {
    training.value = false
    ElMessage.error(e.response?.data?.detail || '训练失败')
  }
}

const stopTraining = async () => {
  // 先关闭训练遮罩层，让确认框可见
  training.value = false
  
  try {
    await ElMessageBox.confirm('确定停止训练并删除未完成的模型吗？', '确认', {
      confirmButtonText: '停止',
      cancelButtonText: '继续训练',
      type: 'warning'
    })
    // 用户确认停止
    if (currentTaskId.value) {
      try { await api.post(`/models/train/stop/${currentTaskId.value}`) } catch (e) {}
    }
    trainProgress.value = null
    saveTrainingTaskId(null)
    currentTaskId.value = null
    stopPolling()
    ElMessage.info('训练已停止')
  } catch (e) {
    // 用户点击取消，恢复训练遮罩层
    training.value = true
  }
}



const deleteModel = async (model: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除模型 "${model.name}" 吗？此操作不可撤销。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await api.delete(`/models/${model.id}`)
    ElMessage.success('模型删除成功')
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

// 类别平衡器逻辑
const startBalancing = async () => {
  if (balancerForm.value.dataset_ids.length === 0) {
    ElMessage.warning('请选择至少一个数据集')
    return
  }
  if (!balancerForm.value.output_name) {
    ElMessage.warning('请输入新文件命名')
    return
  }
  
  try {
    balancing.value = true
    balancerProgress.value = null
    const res = await api.post('/datasets/balance', balancerForm.value)
    currentBalanceTaskId = res.data.task_id
    ElMessage.success('平衡任务已启动，请等待...')
    startBalancerPolling()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '启动失败')
    balancing.value = false
  }
}

const pollBalancerProgress = async () => {
  if (!currentBalanceTaskId) return
  try {
    const res = await api.get(`/datasets/balance/progress/${currentBalanceTaskId}`)
    balancerProgress.value = res.data
    
    if (res.data.stage === 'complete') {
      stopBalancerPolling()
      balancing.value = false
      ElMessage.success('数据平衡成功！')
      await loadData() // 刷新数据集列表
    } else if (res.data.stage === 'error') {
      stopBalancerPolling()
      balancing.value = false
      ElMessage.error(res.data.message || '平衡失败')
    }
  } catch (e) {
    stopBalancerPolling()
    balancing.value = false
  }
}

const startBalancerPolling = () => {
  if (!balancerInterval) balancerInterval = window.setInterval(pollBalancerProgress, 1000)
}

const stopBalancerPolling = () => {
  if (balancerInterval) {
    clearInterval(balancerInterval)
    balancerInterval = null
  }
}

onBeforeRouteLeave(async () => {
  if (!training.value) return true

  try {
    await ElMessageBox.confirm(
      '训练仍在进行中。离开页面后训练会继续在后台执行，返回训练页时会自动恢复进度显示，确定继续离开吗？',
      '训练进行中',
      {
        confirmButtonText: '继续离开',
        cancelButtonText: '留在当前页',
        type: 'warning'
      }
    )
    return true
  } catch {
    return false
  }
})

onMounted(async () => {
  await loadData()
  await restoreTrainingTask()
})
onUnmounted(() => stopPolling())
</script>

<style scoped>
.training-container {
  padding-bottom: 24px;
  position: relative;
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

.action-buttons {
  display: flex;
  gap: 12px;
}

.training-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.training-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.training-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.training-container :deep(.el-table) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
}

.training-container :deep(.el-table th) {
  background: #fafafa;
  color: #606266;
  font-weight: 500;
}

.training-container :deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafafa;
}

.form-card, .list-card {
  margin-bottom: 24px;
}

.train-result {
  margin-top: 20px;
}

.training-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
}

.training-modal {
  width: 450px;
  text-align: center;
  padding: 32px;
}

.training-modal h2 {
  margin-bottom: 24px;
  color: #1f63c2;
  font-size: 20px;
  font-weight: 600;
}

.progress-info {
  margin: 24px 0;
}

.progress-message {
  font-size: 15px;
  margin-bottom: 16px;
  color: #606266;
}

.progress-time {
  margin-top: 12px;
  color: #909399;
}

.warning-text {
  margin-top: 16px;
  font-size: 12px;
  color: #ff4d4f;
}
</style>
