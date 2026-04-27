<template>
  <div class="datasets-container">
    <div class="header-actions">
      <h1>数据集管理</h1>
    </div>

    <el-card class="upload-card" shadow="hover">
      <template #header>
        <span>上传数据集(CSV)</span>
      </template>
      <el-form :model="uploadForm" label-width="120px">
        <el-form-item label="名称">
          <el-input v-model="uploadForm.name" placeholder="数据集名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="uploadForm.type" placeholder="选择类型" style="width: 240px">
            <el-option label="nsl-kdd" value="nsl-kdd" />
            <el-option label="cic-ids2017" value="cic-ids2017" />
            <el-option label="custom" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="uploadForm.description" type="textarea" />
        </el-form-item>
        <el-form-item label="CSV文件">
          <el-upload
            ref="uploaderRef"
            drag
            :auto-upload="false"
            :on-change="onFileChange"
            accept=".csv"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">拖放CSV文件到此处或<em>点击上传</em></div>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="list-card" shadow="hover">
      <template #header>
        <span>数据集列表</span>
      </template>
      <el-table :data="datasets" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="type" label="类型" width="140" />
        <el-table-column prop="sample_count" label="样本数" width="140" />
        <el-table-column prop="created_at" label="创建时间" width="200">
          <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" type="danger" @click="deleteDataset(scope.row.id)" v-if="systemStore.user?.role === 'admin'">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useSystemStore } from '@/stores/system'

const systemStore = useSystemStore()

const datasets = ref<any[]>([])
const uploadForm = ref({
  name: '',
  type: 'nsl-kdd',
  description: ''
})
const file = ref<File | null>(null)
const uploading = ref(false)
const uploaderRef = ref()

const loadDatasets = async () => {
  const res = await api.get('/datasets/')
  datasets.value = res.data
}

const onFileChange = (uploadFile: any) => {
  file.value = uploadFile.raw
}

const submitUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请选择CSV文件')
    return
  }
  if (!uploadForm.value.name) {
    ElMessage.warning('请输入数据集名称')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    formData.append('name', uploadForm.value.name)
    formData.append('type', uploadForm.value.type)
    formData.append('description', uploadForm.value.description)
    await api.post('/datasets/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('已上传')
    uploadForm.value = { name: '', type: 'nsl-kdd', description: '' }
    file.value = null
    await loadDatasets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const deleteDataset = async (id: number) => {
  try {
    await api.delete(`/datasets/${id}`)
    ElMessage.success('已删除')
    await loadDatasets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const formatTime = (ts: string) => new Date(ts).toLocaleString()

onMounted(() => {
  loadDatasets()
})
</script>

<style scoped>
.datasets-container {
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

.datasets-container :deep(.el-card) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  box-shadow: none;
  border-radius: 2px;
}

.datasets-container :deep(.el-card__header) {
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  padding: 12px 16px;
}

.datasets-container :deep(.el-card__body) {
  padding: 20px 16px;
  background: #fafbfc;
}

.datasets-container :deep(.el-table) {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 2px;
}

.datasets-container :deep(.el-table th) {
  background: #fafafa;
  color: #606266;
  font-weight: 500;
}

.datasets-container :deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafafa;
}

.upload-card, .list-card {
  margin-bottom: 24px;
}
</style>
