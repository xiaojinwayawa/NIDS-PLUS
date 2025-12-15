<template>
  <div class="performance-container">
    <div class="header-actions">
      <h1>Model Performance Monitoring</h1>
      <div class="controls">
        <el-select v-model="hours" style="width: 160px" @change="fetchMetrics">
          <el-option label="Last 6 hours" value="6" />
          <el-option label="Last 24 hours" value="24" />
          <el-option label="Last 7 days" value="168" />
        </el-select>
      </div>
    </div>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>Accuracy & F1 Trend</span>
          </template>
          <v-chart class="chart" :option="accChartOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>Precision & Recall Trend</span>
          </template>
          <v-chart class="chart" :option="prChartOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>FPR & FNR Trend</span>
          </template>
          <v-chart class="chart" :option="errorRateOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>Inference Time (ms)</span>
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
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const hours = ref('24')
const metrics = ref<Array<any>>([])

const fetchMetrics = async () => {
  const res = await api.get('/models/metrics', { params: { hours: Number(hours.value) } })
  metrics.value = res.data
}

onMounted(() => {
  fetchMetrics()
})

const timestamps = computed(() => metrics.value.map(m => new Date(m.timestamp).toLocaleString()))
const acc = computed(() => metrics.value.map(m => m.accuracy))
const f1 = computed(() => metrics.value.map(m => m.f1))
const precision = computed(() => metrics.value.map(m => m.precision))
const recall = computed(() => metrics.value.map(m => m.recall))
const fpr = computed(() => metrics.value.map(m => m.fpr ?? null))
const fnr = computed(() => metrics.value.map(m => m.fnr ?? null))
const latency = computed(() => metrics.value.map(m => m.inference_time_ms ?? null))

const accChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['Accuracy', 'F1'] },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value', min: 0, max: 1 },
  series: [
    { name: 'Accuracy', type: 'line', data: acc.value, smooth: true },
    { name: 'F1', type: 'line', data: f1.value, smooth: true }
  ]
}))

const prChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['Precision', 'Recall'] },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value', min: 0, max: 1 },
  series: [
    { name: 'Precision', type: 'line', data: precision.value, smooth: true },
    { name: 'Recall', type: 'line', data: recall.value, smooth: true }
  ]
}))

const errorRateOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['FPR', 'FNR'] },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value', min: 0, max: 1 },
  series: [
    { name: 'FPR', type: 'line', data: fpr.value, smooth: true },
    { name: 'FNR', type: 'line', data: fnr.value, smooth: true }
  ]
}))

const latencyOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['Inference Time (ms)'] },
  xAxis: { type: 'category', data: timestamps.value },
  yAxis: { type: 'value' },
  series: [
    { name: 'Inference Time (ms)', type: 'line', data: latency.value, smooth: true }
  ]
}))
</script>

<style scoped>
.performance-container {
  padding-bottom: 20px;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.charts-row {
  margin-bottom: 20px;
}
.chart {
  width: 100%;
  height: 360px;
}
</style>
