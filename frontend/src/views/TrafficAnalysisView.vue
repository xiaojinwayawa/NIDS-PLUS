<template>
  <div class="traffic-container">
    <div class="header-actions">
      <h1>Traffic Analysis</h1>
      <el-select v-model="timeRange" placeholder="Select time range" @change="fetchData">
        <el-option label="Last 1 Hour" value="1h" />
        <el-option label="Last 24 Hours" value="24h" />
        <el-option label="Last 7 Days" value="7d" />
      </el-select>
    </div>

    <el-row :gutter="20" class="charts-row">
      <!-- Protocol Distribution -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>Protocol Distribution</span>
            </div>
          </template>
          <div class="chart-container">
            <v-chart class="chart" :option="protocolChartOption" autoresize />
          </div>
        </el-card>
      </el-col>
      
      <!-- Port Activity Heatmap -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>Port Activity (Heatmap)</span>
            </div>
          </template>
          <div class="chart-container">
            <v-chart class="chart" :option="heatmapOption" autoresize />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Top IPs Table -->
    <el-row>
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>Top Source IPs</span>
            </div>
          </template>
          <el-table :data="topIps" style="width: 100%" stripe>
            <el-table-column prop="ip" label="IP Address" width="180" />
            <el-table-column prop="country" label="Location" width="180" />
            <el-table-column prop="count" label="Packet Count" sortable>
              <template #default="scope">
                <el-progress 
                  :percentage="Math.min(scope.row.count / maxCount * 100, 100)" 
                  :format="() => scope.row.count"
                />
              </template>
            </el-table-column>
          </el-table>
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
import { PieChart, HeatmapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  VisualMapComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  PieChart,
  HeatmapChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  VisualMapComponent
])

const timeRange = ref('1h')
const protocols = ref<{name: string, value: number}[]>([])
const topIps = ref<{ip: string, count: number, country: string}[]>([])
const heatmapData = ref<[number, number, number][]>([])
const heatmapPorts = ref<string[]>([])
const heatmapTimes = ref<string[]>([])

const maxCount = computed(() => {
  if (topIps.value.length === 0) return 100
  return Math.max(...topIps.value.map(i => i.count))
})

const fetchData = async () => {
  try {
    const response = await api.get('/stats/traffic', {
      params: { time_range: timeRange.value }
    })
    const data = response.data
    
    protocols.value = data.protocols
    topIps.value = data.top_ips
    heatmapData.value = data.heatmap
    heatmapPorts.value = data.ports
    heatmapTimes.value = data.time_slots
  } catch (error) {
    console.error("Failed to fetch traffic stats", error)
  }
}

onMounted(() => {
  fetchData()
})

// Chart Options
const protocolChartOption = computed(() => ({
  tooltip: {
    trigger: 'item'
  },
  legend: {
    orient: 'vertical',
    left: 'left'
  },
  series: [
    {
      name: 'Protocol',
      type: 'pie',
      radius: '50%',
      data: protocols.value,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }
  ]
}))

const heatmapOption = computed(() => ({
  tooltip: {
    position: 'top'
  },
  grid: {
    height: '70%',
    top: '10%'
  },
  xAxis: {
    type: 'category',
    data: heatmapTimes.value,
    splitArea: {
      show: true
    }
  },
  yAxis: {
    type: 'category',
    data: heatmapPorts.value,
    splitArea: {
      show: true
    }
  },
  visualMap: {
    min: 0,
    max: 100, // Adjust based on data
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: '0%'
  },
  series: [
    {
      name: 'Activity',
      type: 'heatmap',
      data: heatmapData.value,
      label: {
        show: true
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }
  ]
}))
</script>

<style scoped>
.traffic-container {
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

.chart-container {
  height: 400px;
}

.chart {
  height: 100%;
  width: 100%;
}
</style>
