<template>
  <div class="performance-container">
    <div class="header-actions">
      <h1>模型性能监控</h1>
      <div class="controls">
        <el-select v-model="selectedModelId" placeholder="选择一个模型" style="width: 300px" @change="selectModel">
          <el-option v-for="model in availableModels" :key="model.id" :label="model.display_name || model.name" :value="model.id" />
        </el-select>
        <el-button type="primary" @click="loadAvailableModels">刷新模型</el-button>
        <el-select v-model="hours" style="width: 160px" @change="fetchMetrics">
          <el-option label="最近6小时" value="6" />
          <el-option label="最近24小时" value="24" />
          <el-option label="最近7天" value="168" />
        </el-select>
      </div>
    </div>

    <el-card v-if="selectedModel" class="model-info-card" shadow="hover">
      <template #header><span>已选模型: {{ selectedModel.name }}</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="类型">{{ selectedModel.type }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ selectedModel.source }}</el-descriptions-item>
        <el-descriptions-item label="时间戳">{{ selectedModel.timestamp ? new Date(selectedModel.timestamp).toLocaleString() : '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>准确率和F1趋势</span>
          </template>
          <v-chart class="chart" :option="accChartOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>精确率和召回率趋势</span>
          </template>
          <v-chart class="chart" :option="prChartOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>推理时间(毫秒)</span>
          </template>
          <v-chart class="chart" :option="latencyOption" autoresize />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const hours = ref('24')
const metrics = ref<Array<any>>([])
const availableModels = ref<any[]>([])
const selectedModelId = ref<string | null>(null)
const selectedModel = ref<any | null>(null)

const loadAvailableModels = async () => {
  try {
    const res = await api.get('/models/available')
    availableModels.value = res.data.models
    ElMessage.success('模型加载成功！')
  } catch (e: any) {
    ElMessage.error('加载可用模型失败')
  }
}

const selectModel = () => {
  if (selectedModelId.value) {
    selectedModel.value = availableModels.value.find(m => m.id === selectedModelId.value) || null
  } else {
    selectedModel.value = null
  }
}

const fetchMetrics = async () => {
  const res = await api.get('/models/metrics', { params: { hours: Number(hours.value) } })
  metrics.value = res.data
}

onMounted(() => {
  fetchMetrics()
  loadAvailableModels()
})

const timestamps = computed(() => metrics.value.map(m => new Date(m.timestamp).toLocaleString()))
const acc = computed(() => metrics.value.map(m => m.accuracy))
const f1 = computed(() => metrics.value.map(m => m.f1))
const precision = computed(() => metrics.value.map(m => m.precision))
const recall = computed(() => metrics.value.map(m => m.recall))
const latency = computed(() => metrics.value.map(m => m.inference_time_ms ?? null))

const accChartOption = computed(() => {
  if (selectedModel.value && selectedModel.value.metrics) {
    const m = selectedModel.value.metrics
    const hasAccuracy = m.accuracy !== undefined && m.accuracy !== null
    const hasF1 = m.f1 !== undefined && m.f1 !== null
    
    const categories: string[] = []
    const data: any[] = []
    
    if (hasAccuracy) {
      categories.push('Accuracy')
      data.push({ value: m.accuracy, itemStyle: { color: '#5470c6' } })
    }
    if (hasF1) {
      categories.push('F1')
      data.push({ value: m.f1, itemStyle: { color: '#91cc75' } })
    }
    
    if (categories.length === 0) {
      categories.push('No metrics data')
      data.push({ value: 0, itemStyle: { color: '#d3d3d3' } })
    }
    
    return {
      tooltip: { trigger: 'item' },
      title: { text: 'Model Metrics', left: 'center' },
      xAxis: { type: 'category', data: categories },
      yAxis: { type: 'value', min: 0, max: 1 },
      series: [
        { 
          name: 'Value', 
          type: 'bar', 
          data: data,
          label: { show: true, formatter: categories[0] === 'No metrics data' ? 'N/A' : '{c}' }
        }
      ]
    }
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Accuracy', 'F1'] },
    xAxis: { type: 'category', data: timestamps.value },
    yAxis: { type: 'value', min: 0, max: 1 },
    series: [
      { name: 'Accuracy', type: 'line', data: acc.value, smooth: true },
      { name: 'F1', type: 'line', data: f1.value, smooth: true }
    ]
  }
})

const prChartOption = computed(() => {
  if (selectedModel.value && selectedModel.value.metrics) {
    const m = selectedModel.value.metrics
    const hasPrecision = m.precision !== undefined && m.precision !== null
    const hasRecall = m.recall !== undefined && m.recall !== null
    
    const categories: string[] = []
    const data: any[] = []
    
    if (hasPrecision) {
      categories.push('Precision')
      data.push({ value: m.precision, itemStyle: { color: '#fac858' } })
    }
    if (hasRecall) {
      categories.push('Recall')
      data.push({ value: m.recall, itemStyle: { color: '#ee6666' } })
    }
    
    if (categories.length === 0) {
      categories.push('No metrics data')
      data.push({ value: 0, itemStyle: { color: '#d3d3d3' } })
    }
    
    return {
      tooltip: { trigger: 'item' },
      title: { text: 'Precision & Recall', left: 'center' },
      xAxis: { type: 'category', data: categories },
      yAxis: { type: 'value', min: 0, max: 1 },
      series: [
        { 
          name: 'Value', 
          type: 'bar', 
          data: data,
          label: { show: true, formatter: categories[0] === 'No metrics data' ? 'N/A' : '{c}' }
        }
      ]
    }
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Precision', 'Recall'] },
    xAxis: { type: 'category', data: timestamps.value },
    yAxis: { type: 'value', min: 0, max: 1 },
    series: [
      { name: 'Precision', type: 'line', data: precision.value, smooth: true },
      { name: 'Recall', type: 'line', data: recall.value, smooth: true }
    ]
  }
})

const latencyOption = computed(() => {
  if (selectedModel.value) {
    if (selectedModel.value.performance) {
      const p = selectedModel.value.performance
      return {
        tooltip: { trigger: 'item' },
        title: { text: 'Performance', left: 'center' },
        xAxis: { type: 'category', data: ['Training Time (s)', 'Inference Time (ms)', 'Throughput (samples/s)'] },
        yAxis: { type: 'value' },
        series: [
          { 
            name: 'Value', 
            type: 'bar', 
            data: [
              { value: p.training_time_sec, itemStyle: { color: '#fc8452' } },
              { value: p.inference_time_ms, itemStyle: { color: '#9a60b4' } },
              { value: p.throughput_samples_per_sec, itemStyle: { color: '#ea7ccc' } }
            ],
            label: { show: true, formatter: '{c}' }
          }
        ]
      }
    } else if (selectedModel.value.metrics) {
      const m = selectedModel.value.metrics
      const hasTrainingTime = m.training_time !== undefined
      return {
        tooltip: { trigger: 'item' },
        title: { text: 'Available Metrics', left: 'center' },
        xAxis: { 
          type: 'category', 
          data: hasTrainingTime ? ['Training Time (s)'] : ['No performance data'] 
        },
        yAxis: { type: 'value' },
        series: [
          { 
            name: 'Value', 
            type: 'bar', 
            data: hasTrainingTime 
              ? [{ value: m.training_time, itemStyle: { color: '#fc8452' } }]
              : [{ value: 0, itemStyle: { color: '#d3d3d3' } }],
            label: { show: true, formatter: hasTrainingTime ? '{c}' : 'N/A' }
          }
        ]
      }
    }
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Inference Time (ms)'] },
    xAxis: { type: 'category', data: timestamps.value },
    yAxis: { type: 'value' },
    series: [
      { name: 'Inference Time (ms)', type: 'line', data: latency.value, smooth: true }
    ]
  }
})
</script>

<style scoped>
.performance-container {
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
  gap: 12px;
  align-items: center;
}

.performance-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.performance-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.performance-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.model-info-card {
  margin-bottom: 24px;
}

.charts-row {
  margin-bottom: 24px;
}

.chart {
  width: 100%;
  height: 360px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 2px;
}
</style>
