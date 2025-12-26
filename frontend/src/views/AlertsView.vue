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
        <el-button type="primary" @click="loadAlerts">Refresh</el-button>
        <el-dropdown @command="handleTestCommand">
          <el-button type="warning">
            Test <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="generate">Generate 10 Test Alerts</el-dropdown-item>
              <el-dropdown-item command="clear" divided>Clear All Alerts</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-card shadow="hover">
      <template #header>
        <div class="card-header-with-tabs">
          <el-tabs v-model="activeTab" @tab-click="onTabChange">
            <el-tab-pane label="Alerts" name="alerts" />
            <el-tab-pane label="FP Governance" name="governance" />
          </el-tabs>
        </div>
      </template>
      
      <!-- Alerts Tab -->
      <div v-if="activeTab === 'alerts'">
        <el-table :data="pagedAlerts" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="timestamp" label="Time" min-width="170">
          <template #default="scope">
            {{ formatTime(scope.row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="src_ip" label="Source IP" min-width="140" />
        <el-table-column prop="dst_ip" label="Destination IP" min-width="150" />
        <el-table-column prop="protocol" label="Protocol" min-width="90" />
        <el-table-column prop="attack_type" label="Attack Type" min-width="140" />
        <el-table-column prop="confidence" label="Confidence" min-width="110">
          <template #default="scope">
            <el-tag :type="confidenceType(scope.row.confidence)">{{ scope.row.confidence.toFixed(2) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
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
      </div>
      
      <!-- FP Governance Tab -->
      <div v-if="activeTab === 'governance'">
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="governance-section">
              <h3>Governance Rules</h3>
              <el-table :data="governanceRules" style="width: 100%" size="small">
                <el-table-column prop="rule_id" label="Rule ID" width="180" />
                <el-table-column prop="rule_type" label="Type" width="100">
                  <template #default="scope">
                    <el-tag size="small">{{ scope.row.rule_type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Details" min-width="150">
                  <template #default="scope">
                    <span v-if="scope.row.whitelist_ips?.length">IPs: {{ scope.row.whitelist_ips.join(', ') }}</span>
                    <span v-else-if="scope.row.whitelist_ports?.length">Ports: {{ scope.row.whitelist_ports.join(', ') }}</span>
                    <span v-else-if="scope.row.feature_name">{{ scope.row.feature_name }} {{ scope.row.feature_condition }} {{ scope.row.feature_value }}</span>
                    <span v-else-if="scope.row.threshold_adjustment">Threshold +{{ scope.row.threshold_adjustment }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="fp_prevented" label="FP Prevented" width="100" />
                <el-table-column prop="is_active" label="Active" width="80">
                  <template #default="scope">
                    <el-switch v-model="scope.row.is_active" size="small" @change="toggleRule(scope.row)" />
                  </template>
                </el-table-column>
                <el-table-column label="Actions" width="80">
                  <template #default="scope">
                    <el-button size="small" type="danger" text @click="deleteRule(scope.row.rule_id)">Delete</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="governance-section">
              <h3>Suggestions</h3>
              <div v-if="governanceSuggestions.length === 0" class="no-data">No suggestions available</div>
              <div v-for="(suggestion, idx) in governanceSuggestions" :key="idx" class="suggestion-item">
                <div class="suggestion-header">
                  <el-tag :type="suggestionTagType(suggestion.type)" size="small">{{ suggestion.type }}</el-tag>
                  <span class="suggestion-confidence">Confidence: {{ (suggestion.confidence * 100).toFixed(0) }}%</span>
                </div>
                <p class="suggestion-desc">{{ suggestion.description }}</p>
                <el-button size="small" type="primary" @click="applySuggestion(suggestion)">Apply</el-button>
              </div>
            </div>
          </el-col>
        </el-row>
        
        <el-divider />
        
        <div class="governance-section">
          <h3>FP/FN Metrics Comparison</h3>
          <div v-if="metricsComparison">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-statistic title="FP Before Rules" :value="metricsComparison.period_before?.false_positives || 0" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="FP After Rules" :value="metricsComparison.period_after?.false_positives || 0" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="FP Prevented" :value="metricsComparison.period_after?.fp_prevented_by_rules || 0" class="success-stat" />
              </el-col>
            </el-row>
            <div v-if="metricsComparison.improvement" class="improvement-info">
              <el-tag type="success" v-if="metricsComparison.improvement.fp_reduction > 0">
                {{ metricsComparison.improvement.fp_reduction_percent.toFixed(1) }}% FP Reduction
              </el-tag>
            </div>
          </div>
          <div v-else class="no-data">No metrics data available</div>
        </div>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
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

// FP Governance
const activeTab = ref('alerts')
const governanceRules = ref<any[]>([])
const governanceSuggestions = ref<any[]>([])
const metricsComparison = ref<any>(null)

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

// Test functions
const handleTestCommand = async (command: string) => {
  if (command === 'generate') {
    await generateTestAlerts()
  } else if (command === 'clear') {
    await clearAllAlerts()
  }
}

const generateTestAlerts = async () => {
  try {
    const res = await api.post('/alerts/test/generate?count=10')
    ElMessage.success(res.data.message)
    await loadAlerts()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to generate test alerts')
  }
}

const clearAllAlerts = async () => {
  try {
    await ElMessageBox.confirm('Are you sure you want to delete all alerts?', 'Warning', {
      confirmButtonText: 'Yes',
      cancelButtonText: 'Cancel',
      type: 'warning'
    })
    const res = await api.delete('/alerts/test/clear')
    ElMessage.success(res.data.message)
    await loadAlerts()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || 'Failed to clear alerts')
    }
  }
}

onMounted(() => {
  loadAlerts()
})

// FP Governance functions
const onTabChange = () => {
  if (activeTab.value === 'governance') {
    loadGovernanceData()
  }
}

const loadGovernanceData = async () => {
  try {
    const [rulesRes, suggestionsRes, metricsRes] = await Promise.all([
      api.get('/alerts/governance/rules'),
      api.get('/alerts/governance/suggestions'),
      api.get('/alerts/governance/metrics')
    ])
    governanceRules.value = rulesRes.data
    governanceSuggestions.value = suggestionsRes.data
    metricsComparison.value = metricsRes.data
  } catch (e: any) {
    console.error('Failed to load governance data', e)
  }
}

const toggleRule = async (rule: any) => {
  try {
    await api.put(`/alerts/governance/rules/${rule.rule_id}/toggle`, { is_active: rule.is_active })
    ElMessage.success('Rule updated')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to update rule')
  }
}

const deleteRule = async (ruleId: string) => {
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this rule?', 'Warning', {
      confirmButtonText: 'Yes',
      cancelButtonText: 'Cancel',
      type: 'warning'
    })
    await api.delete(`/alerts/governance/rules/${ruleId}`)
    ElMessage.success('Rule deleted')
    await loadGovernanceData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || 'Failed to delete rule')
    }
  }
}

const applySuggestion = async (suggestion: any) => {
  try {
    await api.post('/alerts/governance/apply-suggestion', suggestion)
    ElMessage.success('Suggestion applied')
    await loadGovernanceData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to apply suggestion')
  }
}

const suggestionTagType = (type: string) => {
  switch (type) {
    case 'whitelist_ip': return 'primary'
    case 'whitelist_port': return 'success'
    case 'threshold': return 'warning'
    case 'feature_rule': return 'info'
    default: return 'info'
  }
}
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
.card-header-with-tabs {
  margin: -20px -20px 0 -20px;
}
.governance-section {
  margin-bottom: 20px;
}
.governance-section h3 {
  margin-bottom: 12px;
  font-size: 16px;
  color: #303133;
}
.suggestion-item {
  padding: 12px;
  margin-bottom: 10px;
  background: #f5f7fa;
  border-radius: 6px;
}
.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.suggestion-confidence {
  font-size: 12px;
  color: #909399;
}
.suggestion-desc {
  margin: 8px 0;
  font-size: 13px;
  color: #606266;
}
.no-data {
  color: #909399;
  text-align: center;
  padding: 20px;
}
.improvement-info {
  margin-top: 16px;
  text-align: center;
}
.success-stat :deep(.el-statistic__number) {
  color: #67c23a;
}
</style>
