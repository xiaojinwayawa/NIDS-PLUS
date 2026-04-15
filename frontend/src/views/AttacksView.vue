<template>
  <div class="attacks-container">
    <div class="header-actions">
      <h1>攻击类型统计</h1>
      <div class="controls">
        <el-select v-model="hours" style="width: 160px" @change="fetchData">
          <el-option label="最近6小时" value="6" />
          <el-option label="最近24小时" value="24" />
          <el-option label="最近7天" value="168" />
        </el-select>
        <el-button @click="fetchData" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="warning"
      show-icon
      style="margin-bottom: 16px"
    />

    <el-row :gutter="20" v-loading="loading">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>分布</span>
          </template>
          <el-empty v-if="!loading && distribution.length === 0" description="暂无攻击分布数据" :image-size="80" />
          <v-chart v-else class="chart" :option="pieOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>趋势</span>
          </template>
          <el-empty v-if="!loading && timeCounts.length === 0" description="暂无攻击趋势数据" :image-size="80" />
          <v-chart v-else class="chart" :option="lineOption" autoresize />
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
import { PieChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const hours = ref('24')
const distribution = ref<Array<{name:string, value:number}>>([])
const timeLabels = ref<string[]>([])
const timeCounts = ref<number[]>([])
const loading = ref(false)
const errorMessage = ref('')

const fetchData = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await api.get('/stats/attacks', { params: { hours: Number(hours.value) } })
    distribution.value = Array.isArray(res.data.distribution) ? res.data.distribution : []
    timeLabels.value = Array.isArray(res.data.time_labels) ? res.data.time_labels : []
    timeCounts.value = Array.isArray(res.data.time_counts) ? res.data.time_counts : []
  } catch (e: any) {
    distribution.value = []
    timeLabels.value = []
    timeCounts.value = []
    errorMessage.value = e.response?.data?.detail || '攻击统计数据加载失败'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchData())

const pieOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { orient: 'vertical', left: 'left' },
  series: [{ type: 'pie', radius: '60%', data: distribution.value }]
}))

const lineOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: timeLabels.value },
  yAxis: { type: 'value' },
  series: [{ name: 'Alerts', type: 'line', data: timeCounts.value, smooth: true }]
}))
</script>

<style scoped>
.attacks-container {
  padding-bottom: 24px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-actions h1 {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.attacks-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.attacks-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.attacks-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.chart {
  width: 100%;
  height: 360px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 2px;
}
</style>
