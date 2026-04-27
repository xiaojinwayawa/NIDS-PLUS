<template>
  <div class="users-container">
    <div class="header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <el-button type="success" @click="showAddDialog = true" v-if="systemStore.user?.role === 'admin'">
          <el-icon><Plus /></el-icon> 新增用户
        </el-button>
        <el-button type="primary" @click="fetchUsers">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <el-card class="users-card">
      <el-table 
        :data="users" 
        style="width: 100%" 
        v-loading="loading"
        border
        stripe
      >
        <el-table-column prop="id" label="ID" width="80" align="center" />
        
        <el-table-column prop="username" label="用户名" min-width="150">
          <template #default="scope">
            {{ scope.row.username }}
            <el-tag 
              v-if="scope.row.role === 'admin'" 
              type="danger" 
              size="small" 
              class="role-tag"
            >
              超管
            </el-tag>
            <el-tag 
              v-else 
              type="info" 
              size="small" 
              class="role-tag"
            >
              普通用户
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="email" label="邮箱" min-width="200">
          <template #default="scope">
            {{ scope.row.email || '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="is_active" label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
              {{ scope.row.is_active ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="scope">
            <el-button 
              v-if="scope.row.role !== 'admin'"
              size="small" 
              type="success"
              @click="updateRole(scope.row.id, 'admin')"
              :disabled="scope.row.id === systemStore.user?.user_id"
            >
              赋予超管
            </el-button>
            <el-button 
              v-else
              size="small" 
              type="warning"
              @click="updateRole(scope.row.id, 'user')"
              :disabled="scope.row.username === 'admin' || scope.row.id === systemStore.user?.user_id"
            >
              取消超管
            </el-button>
            
            <el-popconfirm
              title="确定要删除该用户吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              confirm-button-type="danger"
              @confirm="deleteUser(scope.row.id)"
              :disabled="scope.row.username === 'admin' || scope.row.id === systemStore.user?.user_id"
            >
              <template #reference>
                <el-button 
                  size="small" 
                  type="danger"
                  :disabled="scope.row.username === 'admin' || scope.row.id === systemStore.user?.user_id"
                  style="margin-left: 10px;"
                >
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddDialog" title="新增用户" width="400px" @close="resetAddForm">
      <el-form 
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        label-width="80px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="addForm.username" placeholder="请输入用户名" />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input v-model="addForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="addForm.email" placeholder="选填，请输入邮箱" />
        </el-form-item>

        <el-form-item label="角色" prop="role">
          <el-select v-model="addForm.role" placeholder="选择角色" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="超管" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAddDialog = false">取消</el-button>
          <el-button type="primary" @click="handleAddUser" :loading="addLoading">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import api from '@/api'
import { useSystemStore } from '@/stores/system'
import { useRouter } from 'vue-router'

const systemStore = useSystemStore()
const router = useRouter()

const users = ref<any[]>([])
const loading = ref(false)

const showAddDialog = ref(false)
const addLoading = ref(false)
const addFormRef = ref<FormInstance>()

const addForm = reactive({
  username: '',
  password: '',
  email: '',
  role: 'user'
})

const addRules = reactive<FormRules>({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
})

const resetAddForm = () => {
  if (addFormRef.value) {
    addFormRef.value.resetFields()
  }
}

const handleAddUser = async () => {
  if (!addFormRef.value) return
  
  await addFormRef.value.validate(async (valid) => {
    if (valid) {
      addLoading.value = true
      try {
        await api.post('/users/', addForm)
        ElMessage.success('用户添加成功')
        showAddDialog.value = false
        await fetchUsers()
      } catch (error: any) {
        ElMessage.error(error.response?.data?.detail || '添加用户失败')
      } finally {
        addLoading.value = false
      }
    }
  })
}

const checkPermission = () => {
  if (systemStore.user?.role !== 'admin') {
    // Return false, but do not redirect. Just show empty state to regular users.
    return false
  }
  return true
}

const fetchUsers = async () => {
  if (!checkPermission()) return
  
  loading.value = true
  try {
    const res = await api.get('/users/')
    users.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const updateRole = async (userId: number, role: string) => {
  try {
    await api.put(`/users/${userId}/role?role=${role}`)
    ElMessage.success(`角色更新成功`)
    await fetchUsers()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '角色更新失败')
  }
}

const deleteUser = async (userId: number) => {
  try {
    await api.delete(`/users/${userId}`)
    ElMessage.success('用户已删除')
    await fetchUsers()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '删除用户失败')
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.users-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h2 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.users-card {
  margin-top: 10px;
}

.role-tag {
  margin-left: 8px;
}
</style>
