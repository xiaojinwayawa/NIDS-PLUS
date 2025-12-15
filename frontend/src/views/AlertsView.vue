<template>
  <div class="alerts-container">
    <div class="header-actions">
      <h1>Alerts</h1>
      <div class="filters">
        <el-input v-model="searchAttack" placeholder="Filter by attack type" clearable style="width: 240px" @input="applyFilter" />
        <el-select v-model="severityFilter" placeholder="Severity" clearable style="width: 160px" @change="applyFilter">
          <el-option label="High" value="high" />
          <el-option label="Medium" value="medium" />
          <el-option label="Low" value="low" />
        </el-select>
      </div>
    </div>

    <el-card shadow="hover">
      <el-table :data="pagedAlerts" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="timestamp" label="Time" width="180">
          <template #default="scope">
            {{ formatTime(scope.row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="src_ip" label="Source IP" width="160" />
        <el-table-column prop="dst_ip" label="Destination IP" width="160" />
        <el-table-column prop="protocol" label="Proto" width="100" />
        <el-table-column prop="attack_type" label="Attack" min-width="160" />
        <el-table-column prop="confidence" label="Conf." width="100">
          <template #default="scope">
            <el-tag :type="confidenceType(scope.row.confidence)">{{ scope.row.confidence.toFixed(2) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="220" fixed="right">
          <template #default="scope">
            <el-button size="small" type="primary" @click="openDetail(scope.row.id)">Details</el-button>
            <el-button size="small" type="warning" :disabled="scope.row.is_false_positive" @click="markFalsePositive(scope.row.id)">
              {{ scope.row.is_false_positive ? 'Marked' : 'Mark False' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :total="filteredAlerts.length"
          :current-page="currentPage"
          :page-size="pageSize"
          :page-sizes="[10,20,50,100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="Alert Detail" width="60%">
      <div v-if="alertDetail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ alertDetail.id }}</el-descriptions-item>
          <el-descriptions-item label="Time">{{ formatTime(alertDetail.timestamp) }}</el-descriptions-item>
          <el-descriptions-item label="Src IP">{{ alertDetail.src_ip }}</el-descriptions-item>
          <el-descriptions-item label="Dst IP">{{ alertDetail.dst_ip }}</el-descriptions-item>
          <el-descriptions-item label="Protocol">{{ alertDetail.protocol }}</el-descriptions-item>
          <el-descriptions-item label="Attack">{{ alertDetail.attack_type }}</el-descriptions-item>
          <el-descriptions-item label="Confidence">{{ alertDetail.confidence.toFixed(2) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <h3>Top Contributing Features (SHAP)</h3>
          <div v-if="shapBarOption" class="chart-wrap">
            <v-chart class="chart" :option="shapBarOption" autoresize />
          </div>
          <div v-else class="no-shap">No SHAP data available</div>
        </div>

        <div class="detail-section">
          <h3>Raw Features</h3>
          <el-table :data="rawFeaturesEntries" style="width: 100%" size="small">
            <el-table-column prop="key" label="Key" width="200" />
            <el-table-column prop="value" label="Value" />
          </el-table>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="detailVisible = false">Close</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

interface AlertRow {
  id: number
  timestamp: string
  src_ip: string
  dst_ip: string
  protocol?: string
  src_port?: number
  dst_port?: number
  attack_type: string
  confidence: number
  is_false_positive: boolean
}

interface AlertDetail {
  id: number
  timestamp: string
  src_ip: string
  dst_ip: string
  src_port?: number
  dst_port?: number
  protocol?: string
  attack_type: string
  confidence: number
  is_false_positive: boolean
  raw_features?: Record<string, any>
  shap_analysis?: {
    top_features?: { feature: string; value: number; shap_value: number; contribution: string }[]
    base_value?: number
  }
}

const alerts = ref<AlertRow[]>([])
const filteredAlerts = ref<AlertRow[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const searchAttack = ref('')
const severityFilter = ref<'high' | 'medium' | 'low' | ''>('')

const detailVisible = ref(false)
const alertDetail = ref<AlertDetail | null>(null)

const pagedAlerts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredAlerts.value.slice(start, start + pageSize.value)
})

const loadAlerts = async () => {
  try {
    const res = await api.get('/alerts/', { params: { limit: 500 } })
    alerts.value = res.data
    filteredAlerts.value = alerts.value
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to load alerts')
  }
}

const applyFilter = () => {
  filteredAlerts.value = alerts.value.filter(a => {
    const matchAttack = searchAttack.value ? a.attack_type.toLowerCase().includes(searchAttack.value.toLowerCase()) : true
    const severity = getSeverity(a.confidence)
    const matchSeverity = severityFilter.value ? severity === severityFilter.value : true
    return matchAttack && matchSeverity
  })
  currentPage.value = 1
}

const onPageChange = (page: number) => {
  currentPage.value = page
}
const onSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const confidenceType = (c: number) => {
  if (c >= 0.9) return 'danger'
  if (c >= 0.7) return 'warning'
  return 'success'
}
const getSeverity = (c: number): 'high' | 'medium' | 'low' => {
  if (c >= 0.9) return 'high'
  if (c >= 0.7) return 'medium'
  return 'low'
}
const formatTime = (ts: string) => {
  return new Date(ts).toLocaleString()
}

const openDetail = async (id: number) => {
  try {
    const res = await api.get(`/alerts/${id}`)
    alertDetail.value = res.data
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to load alert detail')
  }
}

const markFalsePositive = async (id: number) => {
  try {
    await api.post(`/alerts/${id}/false_positive`)
    ElMessage.success('Marked as false positive')
    await loadAlerts()
    applyFilter()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to mark alert')
  }
}

const rawFeaturesEntries = computed(() => {
  const rf = alertDetail.value?.raw_features || {}
  return Object.keys(rf).map(k => ({ key: k, value: typeof rf[k] === 'object' ? JSON.stringify(rf[k]) : rf[k] }))
})

const shapBarOption = computed(() => {
  const tf = alertDetail.value?.shap_analysis?.top_features || []
  if (!tf.length) return null
  const names = tf.map(i => i.feature).reverse()
  const values = tf.map(i => i.shap_value).reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names },
    series: [{ name: 'SHAP', type: 'bar', data: values }]
  }
})

onMounted(() => {
  loadAlerts()
})
</script>

<style scoped>
.alerts-container {
  padding-bottom: 20px;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.filters {
  display: flex;
  gap: 12px;
  align-items: center;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0;
}
.detail-section {
  margin-top: 20px;
}
.chart-wrap {
  height: 300px;
}
.chart {
  height: 100%;
  width: 100%;
}
.no-shap {
  color: #909399;
}
</style>
