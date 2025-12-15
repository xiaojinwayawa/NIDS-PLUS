<template>
  <div class="dashboard-container">
    <div class="header-actions">
      <h1>Dashboard</h1>
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
            Start
          </el-button>
          <el-button 
            type="danger" 
            :icon="VideoPause" 
            :disabled="systemStore.systemState !== 'running'"
            @click="handleStop"
          >
            Stop
          </el-button>
        </el-button-group>
      </div>
    </div>

    <el-row :gutter="20" class="status-cards">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>Current Throughput</span>
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
              <span>Latency</span>
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
              <span>Threat Level</span>
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
              <span>Real-time Traffic</span>
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
              <span>Recent Alerts</span>
            </div>
          </template>
          <div class="alerts-list">
            <div v-if="systemStore.recentAlerts.length === 0" class="no-alerts">
              No recent alerts
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

    <!-- Start Dialog -->
    <el-dialog v-model="startDialogVisible" title="Start Detection System" width="30%">
      <el-form :model="startForm" label-width="100px">
        <el-form-item label="Mode">
          <el-select v-model="startForm.mode">
            <el-option label="PCAP Replay" value="pcap" />
            <el-option label="Live Capture" value="live" />
          </el-select>
        </el-form-item>
        <el-form-item label="Source" v-if="startForm.mode === 'pcap'">
           <el-input v-model="startForm.source" placeholder="Path to PCAP file (optional)" />
        </el-form-item>
        <el-form-item label="Interface" v-if="startForm.mode === 'live'">
           <el-input v-model="startForm.source" placeholder="Network Interface (e.g., eth0)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="startDialogVisible = false">Cancel</el-button>
          <el-button type="primary" @click="confirmStart">Start</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
import { useSystemStore } from '@/stores/system'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
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

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
])

const systemStore = useSystemStore()
const startDialogVisible = ref(false)
const startForm = reactive({
  mode: 'pcap',
  source: ''
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

onMounted(() => {
  systemStore.connectWebSocket()
})

onUnmounted(() => {
  systemStore.disconnectWebSocket()
})

const handleStart = () => {
  startDialogVisible.value = true
}

const confirmStart = async () => {
  try {
    await systemStore.startSystem(startForm.mode, startForm.source || undefined)
    ElMessage.success('System start command sent')
    startDialogVisible.value = false
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to start system')
  }
}

const handleStop = async () => {
  try {
    await systemStore.stopSystem()
    ElMessage.success('System stop command sent')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to stop system')
  }
}

const formatTime = (ts: string) => {
  return new Date(ts).toLocaleTimeString()
}
</script>

<style scoped>
.dashboard-container {
  padding-bottom: 20px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

.status-cards {
  margin-bottom: 20px;
}

.card-value {
  font-size: 28px;
  font-weight: bold;
  text-align: center;
  color: #303133;
}

.unit {
  font-size: 14px;
  color: #909399;
  font-weight: normal;
}

.threat-high .card-value { color: #f56c6c; }
.threat-medium .card-value { color: #e6a23c; }
.threat-low .card-value { color: #67c23a; }

.charts-row {
  margin-bottom: 20px;
}

.chart-container {
  height: 350px;
}

.chart {
  height: 100%;
  width: 100%;
}

.alerts-list {
  height: 350px;
  overflow-y: auto;
}

.no-alerts {
  text-align: center;
  color: #909399;
  padding-top: 50px;
}

.alert-item {
  padding: 10px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-item.critical { border-left: 4px solid #8b0000; background-color: #fef0f0; }
.alert-item.high { border-left: 4px solid #f56c6c; background-color: #fef0f0; }
.alert-item.medium { border-left: 4px solid #e6a23c; background-color: #fdf6ec; }
.alert-item.low { border-left: 4px solid #67c23a; background-color: #f0f9eb; }

.alert-time {
  font-size: 12px;
  color: #909399;
  width: 70px;
}

.alert-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.alert-type {
  font-weight: 600;
  font-size: 14px;
}

.alert-src {
  font-size: 12px;
  color: #606266;
}
</style>
