<template>
  <div class="dashboard-container">
    <div class="header-actions">
      <h1>仪表板</h1>
      <div class="controls">
        <el-tag :type="statusType" class="status-tag" size="large" effect="dark">
          {{ systemStore.systemState.toUpperCase() }}
        </el-tag>
        
        <el-button-group>
          <el-button 
            type="success" 
            :icon="VideoPlay" 
            :disabled="systemStore.systemState === 'running'"
            @click="handleStart"
          >
            启动
          </el-button>
          <el-button 
            type="danger" 
            :icon="VideoPause" 
            :disabled="systemStore.systemState !== 'running'"
            @click="handleStop"
          >
            停止
          </el-button>
        </el-button-group>
      </div>
    </div>

    <el-row :gutter="20" class="status-cards">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><DataLine /></el-icon>
              <span>当前吞吐量</span>
            </div>
          </template>
          <div class="card-value">
            {{ systemStore.currentThroughput }} <span class="unit">pkts/s</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Clock /></el-icon>
              <span>延迟</span>
            </div>
          </template>
          <div class="card-value">
            {{ systemStore.currentLatency.toFixed(2) }} <span class="unit">ms</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" :class="threatClass">
          <template #header>
            <div class="card-header">
              <el-icon><Warning /></el-icon>
              <span>威胁等级</span>
            </div>
          </template>
          <div class="card-value">
            {{ systemStore.threatLevel }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>实时流量</span>
            </div>
          </template>
          <div class="chart-container">
            <v-chart class="chart" :option="trafficChartOption" autoresize />
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>近期告警</span>
            </div>
          </template>
          <div class="alerts-list">
            <div v-if="systemStore.recentAlerts.length === 0" class="no-alerts">
              暂无告警
            </div>
            <div v-else class="alert-items">
              <div 
                v-for="(alert, index) in systemStore.recentAlerts" 
                :key="index"
                class="alert-item"
                :class="alert.severity"
              >
                <div class="alert-time">{{ formatTime(alert.timestamp) }}</div>
                <div class="alert-info">
                  <span class="alert-type">{{ alert.attack_type }}</span>
                  <span class="alert-src">{{ alert.src_ip }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 启动对话框 -->
    <el-dialog v-model="startDialogVisible" title="启动检测系统" width="500px" modal-class="app-content-dialog-mask">
      <el-form :model="startForm" label-width="100px">
        <el-form-item label="模型">
          <el-select 
            v-model="startForm.model" 
            placeholder="选择检测模型"
            :loading="loadingModels"
            style="width: 100%"
          >
            <el-option-group
              v-for="group in groupedAvailableModels"
              :key="group.label"
              :label="group.label"
            >
              <el-option 
                v-for="model in group.options" 
                :key="model.name" 
                :label="`${model.display_name || model.name} (${model.type})`"
                :value="model.name"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="模式">
          <el-select v-model="startForm.mode" @change="onModeChange">
            <el-option label="PCAP 回放" value="pcap" />
            <el-option label="实时捕获" value="live" />
          </el-select>
        </el-form-item>
        <el-form-item label="PCAP 文件" v-if="startForm.mode === 'pcap'">
          <el-select 
            v-model="startForm.source" 
            placeholder="选择 PCAP 文件"
            :loading="loadingPcaps"
            style="width: 100%"
          >
            <el-option 
              v-for="file in pcapFiles" 
              :key="file.path" 
              :label="`${file.name} (${file.size_mb} MB)`"
              :value="file.path"
            />
          </el-select>
          <div class="pcap-hint" v-if="pcapDirectory">
            目录: {{ pcapDirectory }}
          </div>
        </el-form-item>
        <el-form-item label="接口" v-if="startForm.mode === 'live'">
          <el-select 
            v-model="startForm.source" 
            placeholder="选择网络接口"
            :loading="loadingInterfaces"
            style="width: 100%"
          >
            <el-option 
              v-for="iface in networkInterfaces" 
              :key="iface" 
              :label="iface === defaultInterface ? `${iface} (默认)` : iface"
              :value="iface"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="startDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmStart" :disabled="!canStart">启动</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
import { useSystemStore } from '@/stores/system'
import { VideoPlay, VideoPause, DataLine, Clock, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components'
import api from '@/api'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
])

interface PcapFile {
  name: string
  path: string
  size: number
  size_mb: number
}

interface ModelInfo {
  name: string
  display_name?: string
  file: string
  type: string
  source?: string
  group?: string
  metadata?: any
}

const systemStore = useSystemStore()
const startDialogVisible = ref(false)
const loadingPcaps = ref(false)
const loadingInterfaces = ref(false)
const loadingModels = ref(false)
const pcapFiles = ref<PcapFile[]>([])
const pcapDirectory = ref('')
const networkInterfaces = ref<string[]>([])
const defaultInterface = ref('')
const availableModels = ref<ModelInfo[]>([])

const startForm = reactive({
  mode: 'pcap',
  source: '',
  model: 'lightgbm_cicids'
})

const canStart = computed(() => {
  if (!startForm.model) {
    return false
  }
  if (startForm.mode === 'pcap') {
    return !!startForm.source
  }
  return true
})

const groupedAvailableModels = computed(() => {
  const groups = [
    {
      label: '单一模型',
      key: 'single',
      options: availableModels.value.filter(model => model.group !== 'experiment')
    },
    {
      label: '实验模型',
      key: 'experiment',
      options: availableModels.value.filter(model => model.group === 'experiment')
    }
  ]

  return groups.filter(group => group.options.length > 0)
})

const statusType = computed(() => {
  switch (systemStore.systemState) {
    case 'running': return 'success'
    case 'stopped': return 'info'
    case 'error': return 'danger'
    default: return 'warning'
  }
})

const threatClass = computed(() => {
  switch (systemStore.threatLevel) {
    case 'High': return 'threat-high'
    case 'Medium': return 'threat-medium'
    default: return 'threat-low'
  }
})

// Chart Options
const trafficChartOption = computed(() => {
  const data = systemStore.trafficHistory
  const timestamps = data.map(d => new Date(d.timestamp).toLocaleTimeString())
  const throughputs = data.map(d => d.throughput)
  const latencies = data.map(d => d.latency)

  return {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['Throughput', 'Latency']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timestamps
    },
    yAxis: [
      {
        type: 'value',
        name: 'Pkts/s',
        position: 'left'
      },
      {
        type: 'value',
        name: 'Latency (ms)',
        position: 'right'
      }
    ],
    series: [
      {
        name: 'Throughput',
        type: 'line',
        data: throughputs,
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.1 }
      },
      {
        name: 'Latency',
        type: 'line',
        yAxisIndex: 1,
        data: latencies,
        smooth: true,
        showSymbol: false
      }
    ]
  }
})

onMounted(async () => {
  // Fetch current system status first
  await systemStore.fetchSystemStatus()
  // Then connect WebSocket for real-time updates
  systemStore.connectWebSocket()
})

onUnmounted(() => {
  systemStore.disconnectWebSocket()
})

const fetchPcapFiles = async () => {
  loadingPcaps.value = true
  try {
    const response = await api.get('/datasets/pcaps')
    pcapFiles.value = response.data.files
    pcapDirectory.value = response.data.directory
    // Auto-select first file if available
    if (pcapFiles.value.length > 0 && !startForm.source) {
      startForm.source = pcapFiles.value[0].path
    }
  } catch (error) {
    console.error('Failed to fetch PCAP files', error)
    ElMessage.warning('无法加载PCAP文件列表')
  } finally {
    loadingPcaps.value = false
  }
}

const fetchNetworkInterfaces = async () => {
  loadingInterfaces.value = true
  try {
    const response = await api.get('/system/interfaces')
    networkInterfaces.value = response.data.interfaces
    defaultInterface.value = response.data.default
    // Auto-select default interface if available
    if (!startForm.source && defaultInterface.value) {
      startForm.source = defaultInterface.value
    } else if (!startForm.source && networkInterfaces.value.length > 0) {
      startForm.source = networkInterfaces.value[0]
    }
  } catch (error) {
    console.error('Failed to fetch network interfaces', error)
    ElMessage.warning('无法加载网络接口列表')
  } finally {
    loadingInterfaces.value = false
  }
}

const fetchAvailableModels = async () => {
  loadingModels.value = true
  try {
    const response = await api.get('/models/available')
    availableModels.value = response.data.models
    // Auto-select first model if current selection is not in list
    if (availableModels.value.length > 0) {
      const modelNames = availableModels.value.map(m => m.name)
      if (!modelNames.includes(startForm.model)) {
        startForm.model = availableModels.value[0].name
      }
    }
  } catch (error) {
    console.error('Failed to fetch available models', error)
    ElMessage.warning('无法加载模型列表')
  } finally {
    loadingModels.value = false
  }
}

const handleStart = async () => {
  startDialogVisible.value = true
  // Fetch models and PCAP files when dialog opens
  await fetchAvailableModels()
  if (startForm.mode === 'pcap') {
    await fetchPcapFiles()
  }
}

const onModeChange = async (mode: string) => {
  startForm.source = ''
  if (mode === 'pcap') {
    await fetchPcapFiles()
  } else if (mode === 'live') {
    await fetchNetworkInterfaces()
  }
}

const confirmStart = async () => {
  try {
    // First configure the model
    await api.post('/system/configure', { model_name: startForm.model })
    // Then start the system
    await systemStore.startSystem(startForm.mode, startForm.source || undefined)
    ElMessage.success('系统启动命令已发送')
    startDialogVisible.value = false
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动系统失败')
  }
}

const handleStop = async () => {
  try {
    await systemStore.stopSystem()
    ElMessage.success('系统停止命令已发送')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '停止系统失败')
  }
}

const formatTime = (ts: string) => {
  return new Date(ts).toLocaleTimeString()
}
</script>

<style scoped>
.dashboard-container {
  padding-bottom: 24px;
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

.controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-cards {
  margin-bottom: 24px;
}

.status-cards :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.status-cards :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.status-cards :deep(.el-card__body) {
  padding: 20px 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header span {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}

.card-value {
  font-size: 32px;
  font-weight: 600;
  text-align: left;
  color: #303133;
  display: flex;
  align-items: baseline;
}

.unit {
  font-size: 14px;
  color: #909399;
  font-weight: normal;
  margin-left: 6px;
}

.threat-high .card-value { color: #ff4d4f; }
.threat-medium .card-value { color: #faad14; }
.threat-low .card-value { color: #52c41a; }

.charts-row {
  margin-bottom: 24px;
}

.charts-row :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.charts-row :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.charts-row :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.chart-container {
  height: 380px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 2px;
}

.chart {
  height: 100%;
  width: 100%;
}

.alerts-list {
  height: 380px;
  overflow-y: auto;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 2px;
}

.no-alerts {
  text-align: center;
  color: #909399;
  padding-top: 80px;
  font-size: 14px;
}

.alert-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  transition: background-color 0.2s;
}

.alert-item:hover {
  background-color: #fafafa;
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-item.critical { border-left: 3px solid #8b0000; }
.alert-item.high { border-left: 3px solid #ff4d4f; }
.alert-item.medium { border-left: 3px solid #faad14; }
.alert-item.low { border-left: 3px solid #52c41a; }

.alert-time {
  font-size: 12px;
  color: #909399;
  width: 75px;
  flex-shrink: 0;
}

.alert-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-left: 12px;
}

.alert-type {
  font-weight: 500;
  font-size: 14px;
  color: #303133;
}

.alert-src {
  font-size: 13px;
  color: #606266;
}

.pcap-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>
