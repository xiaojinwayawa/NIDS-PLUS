<template>
  <div class="alerts-container">
    <div class="header-actions">
      <h1>告警</h1>
      <div class="filters">
        <el-input v-model="searchAttack" placeholder="按攻击类型过滤" clearable style="width: 240px" @input="applyFilter" />
        <el-select v-model="severityFilter" placeholder="严重程度" clearable style="width: 160px" @change="applyFilter">
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
        <el-button type="primary" :loading="alertsLoading || governanceLoading" @click="refreshCurrentTab">刷新</el-button>
        
        <el-button type="danger" :disabled="selectedAlerts.length === 0" @click="handleBatchDelete">删除选中 ({{ selectedAlerts.length }})</el-button>
        <el-button type="danger" plain @click="handleDeleteAll">全部清空</el-button>
      </div>
    </div>

    <el-card shadow="hover">
      <template #header>
        <div class="card-header-with-tabs">
          <el-tabs v-model="activeTab" @tab-click="onTabChange">
            <el-tab-pane label="告警" name="alerts" />
            <el-tab-pane label="误报管理" name="governance" />
          </el-tabs>
        </div>
      </template>
      
      <!-- Alerts Tab -->
      <div v-if="activeTab === 'alerts'" v-loading="alertsLoading">
        <el-alert
          v-if="alertsError"
          :title="alertsError"
          type="warning"
          show-icon
          style="margin-bottom: 12px"
        />
        <el-table :data="pagedAlerts" style="width: 100%" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="timestamp" label="时间" min-width="170">
          <template #default="scope">
            {{ formatTime(scope.row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="src_ip" label="源IP" min-width="140" />
        <el-table-column prop="dst_ip" label="目标IP" min-width="150" />
        <el-table-column prop="protocol" label="协议" min-width="90" />
        <el-table-column label="攻击类型" min-width="140">
          <template #default="scope">
            {{ cleanAttackType(scope.row.attack_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" min-width="110">
          <template #default="scope">
            <el-tag :type="confidenceType(scope.row.confidence)">{{ scope.row.confidence.toFixed(2) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="scope">
            <div style="display: flex; gap: 8px;">
              <el-button size="small" type="primary" @click="openDetail(scope.row.id)">详情</el-button>
              <el-button size="small" type="warning" :disabled="scope.row.is_false_positive" @click="markFalsePositive(scope.row.id)">
                {{ scope.row.is_false_positive ? '已标记' : '标记误报' }}
              </el-button>
              <el-button size="small" type="danger" @click="deleteAlert(scope.row.id)">删除</el-button>
            </div>
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
      <div v-if="activeTab === 'governance'" v-loading="governanceLoading">
        <el-alert
          v-if="governanceError"
          :title="governanceError"
          type="warning"
          show-icon
          style="margin-bottom: 12px"
        />
        <div class="governance-section">
          <h3>误报告警列表</h3>
          <el-table :data="falsePositiveAlerts" style="width: 100%" stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="timestamp" label="时间" min-width="170">
              <template #default="scope">
                {{ formatTime(scope.row.timestamp) }}
              </template>
            </el-table-column>
            <el-table-column prop="src_ip" label="源IP" min-width="140" />
            <el-table-column prop="dst_ip" label="目标IP" min-width="150" />
            <el-table-column prop="protocol" label="协议" min-width="90" />
            <el-table-column label="攻击类型" min-width="140">
              <template #default="scope">
                {{ cleanAttackType(scope.row.attack_type) }}
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" min-width="110">
              <template #default="scope">
                <el-tag :type="confidenceType(scope.row.confidence)">{{ scope.row.confidence.toFixed(2) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="scope">
                <div style="display: flex; gap: 8px;">
                  <el-button size="small" type="primary" @click="openDetail(scope.row.id)">详情</el-button>
                  <el-button size="small" type="warning" @click="unmarkFalsePositive(scope.row.id)">取消误报</el-button>
                  <el-button size="small" type="danger" @click="deleteAlert(scope.row.id)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="falsePositiveAlerts.length === 0" class="no-data">暂无误报告警</div>
        </div>
        
        <el-divider />
        
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="governance-section">
              <h3>管理规则</h3>
              <el-table :data="governanceRules" style="width: 100%" size="small">
                <el-table-column prop="rule_id" label="规则ID" width="180" />
                <el-table-column prop="rule_type" label="类型" width="100">
                  <template #default="scope">
                    <el-tag size="small">{{ scope.row.rule_type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="详情" min-width="150">
                  <template #default="scope">
                    <span v-if="scope.row.whitelist_ips?.length">IP: {{ scope.row.whitelist_ips.join(', ') }}</span>
                    <span v-else-if="scope.row.whitelist_ports?.length">端口: {{ scope.row.whitelist_ports.join(', ') }}</span>
                    <span v-else-if="scope.row.feature_name">{{ scope.row.feature_name }} {{ scope.row.feature_condition }} {{ scope.row.feature_value }}</span>
                    <span v-else-if="scope.row.threshold_adjustment">阈值 +{{ scope.row.threshold_adjustment }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="fp_prevented" label="避免误报" width="100" />
                <el-table-column prop="is_active" label="启用" width="80">
                  <template #default="scope">
                    <el-switch v-model="scope.row.is_active" size="small" @change="toggleRule(scope.row)" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template #default="scope">
                    <el-button size="small" type="danger" text @click="deleteRule(scope.row.rule_id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="governance-section">
              <h3>建议</h3>
              <div v-if="governanceSuggestions.length === 0" class="no-data">暂无建议</div>
              <div v-for="(suggestion, idx) in governanceSuggestions" :key="idx" class="suggestion-item">
                <div class="suggestion-header">
                  <el-tag :type="suggestionTagType(suggestion.type)" size="small">{{ suggestion.type }}</el-tag>
                  <span class="suggestion-confidence">置信度: {{ (suggestion.confidence * 100).toFixed(0) }}%</span>
                </div>
                <p class="suggestion-desc">{{ suggestion.description }}</p>
                <el-button size="small" type="primary" @click="applySuggestion(suggestion)">应用</el-button>
              </div>
            </div>
          </el-col>
        </el-row>
        
        <el-divider />
        
        <div class="governance-section">
          <h3>误报/漏报指标对比</h3>
          <div v-if="metricsComparison">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-statistic title="规则前误报" :value="metricsComparison.period_before?.false_positives || 0" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="规则后误报" :value="metricsComparison.period_after?.false_positives || 0" />
              </el-col>
              <el-col :span="8">
                <el-statistic title="避免误报数" :value="metricsComparison.period_after?.fp_prevented_by_rules || 0" class="success-stat" />
              </el-col>
            </el-row>
            <div v-if="metricsComparison.improvement" class="improvement-info">
              <el-tag type="success" v-if="metricsComparison.improvement.fp_reduction > 0">
                {{ metricsComparison.improvement.fp_reduction_percent.toFixed(1) }}% 误报降低
              </el-tag>
            </div>
          </div>
          <div v-else-if="!governanceLoading" class="no-data">暂无指标数据</div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="告警详情" width="60%" modal-class="app-content-dialog-mask">
      <div v-if="alertDetail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ alertDetail.id }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ formatTime(alertDetail.timestamp) }}</el-descriptions-item>
          <el-descriptions-item label="源IP">{{ alertDetail.src_ip }}</el-descriptions-item>
          <el-descriptions-item label="目标IP">{{ alertDetail.dst_ip }}</el-descriptions-item>
          <el-descriptions-item label="协议">{{ alertDetail.protocol }}</el-descriptions-item>
          <el-descriptions-item label="攻击">{{ cleanAttackType(alertDetail.attack_type) }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ alertDetail.confidence.toFixed(2) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <h3>主要贡献特征 (SHAP)</h3>
          <div v-if="shapFeatures.length > 0" class="chart-wrap">
            <AlertShapChart :features="shapFeatures" />
          </div>
          <div v-else class="no-shap">暂无SHAP数据</div>
        </div>

        <div class="detail-section">
          <h3>原始特征</h3>
          <el-table :data="rawFeaturesEntries" style="width: 100%" size="small">
            <el-table-column prop="key" label="键" width="200" />
            <el-table-column prop="value" label="值" />
          </el-table>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="detailVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const AlertShapChart = defineAsyncComponent(() => import('@/components/AlertShapChart.vue'))

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
const falsePositiveAlerts = ref<AlertRow[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const searchAttack = ref('')
const severityFilter = ref<'high' | 'medium' | 'low' | ''>('')

const detailVisible = ref(false)
const alertDetail = ref<AlertDetail | null>(null)
const alertsLoading = ref(false)
const governanceLoading = ref(false)
const governanceLoaded = ref(false)
const alertsError = ref('')
const governanceError = ref('')
let alertsRefreshTimer: number | null = null

// FP Governance
const activeTab = ref('alerts')
const governanceRules = ref<any[]>([])
const governanceSuggestions = ref<any[]>([])
const metricsComparison = ref<any>(null)

const selectedAlerts = ref<AlertRow[]>([])

const handleSelectionChange = (val: AlertRow[]) => {
  selectedAlerts.value = val
}

const handleBatchDelete = async () => {
  if (selectedAlerts.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedAlerts.value.length} 条告警吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const ids = selectedAlerts.value.map(a => a.id)
    await api.post('/alerts/batch-delete', { alert_ids: ids })
    ElMessage.success(`已删除 ${ids.length} 条告警`)
    
    selectedAlerts.value = []
    await loadAlerts()
    if (activeTab.value === 'governance') {
      await loadFalsePositiveAlerts()
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '批量删除告警失败')
    }
  }
}

const handleDeleteAll = async () => {
  try {
    await ElMessageBox.confirm('此操作将清空所有告警数据，是否继续？', '危险操作', {
      confirmButtonText: '确定清空',
      cancelButtonText: '取消',
      type: 'error'
    })
    
    const res = await api.post('/alerts/clear-all')
    ElMessage.success('已清空所有告警')
    
    selectedAlerts.value = []
    await loadAlerts()
    if (activeTab.value === 'governance') {
      await loadFalsePositiveAlerts()
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '清空告警失败')
    }
  }
}

const pagedAlerts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredAlerts.value.slice(start, start + pageSize.value)
})

const loadAlerts = async () => {
  if (alertsLoading.value) return
  alertsLoading.value = true
  alertsError.value = ''
  try {
    const res = await api.get('/alerts/', { params: { limit: 500 } })
    alerts.value = res.data
    applyFilter()
  } catch (e: any) {
    alerts.value = []
    filteredAlerts.value = []
    alertsError.value = e.response?.data?.detail || '加载告警失败'
    ElMessage.error(alertsError.value)
  } finally {
    alertsLoading.value = false
  }
}

const startAlertsAutoRefresh = () => {
  if (alertsRefreshTimer) return

  alertsRefreshTimer = window.setInterval(() => {
    if (activeTab.value === 'alerts' && !detailVisible.value) {
      loadAlerts()
    }
  }, 5000)
}

const stopAlertsAutoRefresh = () => {
  if (alertsRefreshTimer) {
    clearInterval(alertsRefreshTimer)
    alertsRefreshTimer = null
  }
}

const loadFalsePositiveAlerts = async () => {
  try {
    const res = await api.get('/alerts/false-positives/list')
    falsePositiveAlerts.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载误报告警失败')
  }
}

const unmarkFalsePositive = async (id: number) => {
  try {
    await api.post(`/alerts/${id}/unmark_false_positive`)
    ElMessage.success('已取消误报标记')
    await loadFalsePositiveAlerts()
    await loadAlerts()
    applyFilter()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '取消误报标记失败')
  }
}

const deleteAlert = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这条告警吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.delete(`/alerts/${id}`)
    ElMessage.success('告警已删除')
    await loadAlerts()
    if (activeTab.value === 'governance') {
      await loadFalsePositiveAlerts()
    }
    applyFilter()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除告警失败')
    }
  }
}

const applyFilter = () => {
  filteredAlerts.value = alerts.value.filter(a => {
    const attackType = a.attack_type || ''
    const matchAttack = searchAttack.value ? attackType.toLowerCase().includes(searchAttack.value.toLowerCase()) : true
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

const cleanAttackType = (type: string) => {
  if (!type) return 'Unknown'
  return type.replace(/_/g, ' ')
}

const openDetail = async (id: number) => {
  try {
    const res = await api.get(`/alerts/${id}`)
    alertDetail.value = res.data
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载告警详情失败')
  }
}

const markFalsePositive = async (id: number) => {
  try {
    await api.post(`/alerts/${id}/false_positive`)
    ElMessage.success('已标记为误报')
    await loadAlerts()
    applyFilter()
    if (activeTab.value === 'governance') {
      await loadFalsePositiveAlerts()
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '标记告警失败')
  }
}

const rawFeaturesEntries = computed(() => {
  const rf = alertDetail.value?.raw_features || {}
  return Object.keys(rf).map(k => ({ key: k, value: typeof rf[k] === 'object' ? JSON.stringify(rf[k]) : rf[k] }))
})

const shapFeatures = computed(() => alertDetail.value?.shap_analysis?.top_features || [])

onMounted(() => {
  requestAnimationFrame(() => {
    loadAlerts()
  })
  startAlertsAutoRefresh()
})

onUnmounted(() => {
  stopAlertsAutoRefresh()
})

// FP Governance functions
const onTabChange = async () => {
  if (activeTab.value === 'governance' && !governanceLoaded.value) {
    await loadGovernanceSection()
  } else if (activeTab.value === 'alerts') {
    await loadAlerts()
  }
}

const loadGovernanceData = async () => {
  governanceError.value = ''
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
    governanceError.value = e.response?.data?.detail || '加载误报管理数据失败'
    console.error('Failed to load governance data', e)
    ElMessage.error(governanceError.value)
  }
}

const loadGovernanceSection = async (force = false) => {
  if (governanceLoading.value) return
  if (governanceLoaded.value && !force) return

  governanceLoading.value = true
  try {
    await Promise.all([loadGovernanceData(), loadFalsePositiveAlerts()])
    governanceLoaded.value = true
  } finally {
    governanceLoading.value = false
  }
}

const refreshCurrentTab = async () => {
  if (activeTab.value === 'governance') {
    await loadGovernanceSection(true)
  } else {
    await loadAlerts()
  }
}

const toggleRule = async (rule: any) => {
  try {
    await api.put(`/alerts/governance/rules/${rule.rule_id}/toggle`, { is_active: rule.is_active })
    ElMessage.success('规则已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新规则失败')
  }
}

const deleteRule = async (ruleId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除此规则吗？', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.delete(`/alerts/governance/rules/${ruleId}`)
    ElMessage.success('规则已删除')
    await loadGovernanceSection(true)
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除规则失败')
    }
  }
}

const applySuggestion = async (suggestion: any) => {
  try {
    await api.post('/alerts/governance/apply-suggestion', suggestion)
    ElMessage.success('建议已应用')
    await loadGovernanceSection(true)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '应用建议失败')
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

.filters {
  display: flex;
  gap: 12px;
  align-items: center;
}

.alerts-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.alerts-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.alerts-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.alerts-container :deep(.el-table) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
}

.alerts-container :deep(.el-table th) {
  background: #fafafa;
  color: #606266;
  font-weight: 500;
}

.alerts-container :deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafafa;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 0 0;
}

.detail-section {
  margin-top: 20px;
}

.chart-wrap {
  height: 300px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 2px;
}

.chart {
  height: 100%;
  width: 100%;
}

.no-shap {
  color: #909399;
  text-align: center;
  padding: 40px 0;
}

.card-header-with-tabs {
  margin: -12px -16px 0 -16px;
}

.governance-section {
  margin-bottom: 24px;
}

.governance-section h3 {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.suggestion-item {
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
  transition: box-shadow 0.2s;
}

.suggestion-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
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
  margin: 8px 0 12px 0;
  font-size: 14px;
  color: #606266;
}

.no-data {
  color: #909399;
  text-align: center;
  padding: 40px 20px;
}

.improvement-info {
  margin-top: 16px;
  text-align: center;
}

.success-stat :deep(.el-statistic__number) {
  color: #52c41a;
}
</style>
