<template>
  <div class="datasets-container">
    <div class="header-actions">
      <h1>Datasets Management</h1>
    </div>

    <el-card class="upload-card" shadow="hover">
      <template #header>
        <span>Upload Dataset (CSV)</span>
      </template>
      <el-form :model="uploadForm" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="uploadForm.name" placeholder="Dataset name" />
        </el-form-item>
        <el-form-item label="Type">
          <el-select v-model="uploadForm.type" placeholder="Select type" style="width: 240px">
            <el-option label="nsl-kdd" value="nsl-kdd" />
            <el-option label="cic-ids2017" value="cic-ids2017" />
            <el-option label="custom" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="uploadForm.description" type="textarea" />
        </el-form-item>
        <el-form-item label="CSV File">
          <el-upload
            ref="uploaderRef"
            drag
            :auto-upload="false"
            :on-change="onFileChange"
            accept=".csv"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">Drop CSV here or <em>click to upload</em></div>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="uploading" @click="submitUpload">Upload</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="list-card" shadow="hover">
      <template #header>
        <span>Dataset List</span>
      </template>
      <el-table :data="datasets" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Name" width="200" />
        <el-table-column prop="type" label="Type" width="140" />
        <el-table-column prop="sample_count" label="Samples" width="140" />
        <el-table-column prop="created_at" label="Created" width="200">
          <template #default="scope">{{ formatTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" type="danger" @click="deleteDataset(scope.row.id)">Delete</el-button>
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
    ElMessage.warning('Please select CSV file')
    return
  }
  if (!uploadForm.value.name) {
    ElMessage.warning('Please input dataset name')
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
    ElMessage.success('Uploaded')
    uploadForm.value = { name: '', type: 'nsl-kdd', description: '' }
    file.value = null
    await loadDatasets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Upload failed')
  } finally {
    uploading.value = false
  }
}

const deleteDataset = async (id: number) => {
  try {
    await api.delete(`/datasets/${id}`)
    ElMessage.success('Deleted')
    await loadDatasets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Delete failed')
  }
}

const formatTime = (ts: string) => new Date(ts).toLocaleString()

onMounted(() => {
  loadDatasets()
})
</script>

<style scoped>
.datasets-container { padding-bottom: 20px; }
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.upload-card, .list-card {
  margin-bottom: 20px;
}
</style>
