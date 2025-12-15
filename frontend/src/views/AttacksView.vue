<template>
  <div class="attacks-container">
    <div class="header-actions">
      <h1>Attack Type Statistics</h1>
      <el-select v-model="hours" style="width: 160px" @change="fetchData">
        <el-option label="Last 6 hours" value="6" />
        <el-option label="Last 24 hours" value="24" />
        <el-option label="Last 7 days" value="168" />
      </el-select>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>Distribution</span>
          </template>
          <v-chart class="chart" :option="pieOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>Trend</span>
          </template>
          <v-chart class="chart" :option="lineOption" autoresize />
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
import { PieChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const hours = ref('24')
const distribution = ref<Array<{name:string, value:number}>>([])
const timeLabels = ref<string[]>([])
const timeCounts = ref<number[]>([])

const fetchData = async () => {
  const res = await api.get('/stats/attacks', { params: { hours: Number(hours.value) } })
  distribution.value = res.data.distribution
  timeLabels.value = res.data.time_labels
  timeCounts.value = res.data.time_counts
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
.attacks-container { padding-bottom: 20px; }
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.chart {
  width: 100%;
  height: 360px;
}
</style>
