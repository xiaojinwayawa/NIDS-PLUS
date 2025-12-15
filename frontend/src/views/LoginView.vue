<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>NIDS System</h1>
        <p>Network Intrusion Detection System</p>
      </div>
      
      <el-form 
        ref="loginFormRef"
        :model="loginForm"
        :rules="rules"
        label-position="top"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="Username" prop="username">
          <el-input 
            v-model="loginForm.username" 
            placeholder="Enter username"
            :prefix-icon="User"
          />
        </el-form-item>
        
        <el-form-item label="Password" prop="password">
          <el-input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="Enter password"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="login-button" 
            :loading="loading"
            @click="handleLogin"
          >
            Login
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <p>Default: admin / admin123</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useSystemStore } from '@/stores/system'

const router = useRouter()
const systemStore = useSystemStore()
const loginFormRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = reactive<FormRules>({
  username: [{ required: true, message: 'Please input username', trigger: 'blur' }],
  password: [{ required: true, message: 'Please input password', trigger: 'blur' }]
})

const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await systemStore.login(loginForm.username, loginForm.password)
        ElMessage.success('Login successful')
        router.push('/')
      } catch (error: any) {
        ElMessage.error(error.response?.data?.detail || 'Login failed')
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f5f7fa;
  /* Optional: Sci-fi background */
  /* background: radial-gradient(circle at center, #1b2735 0%, #090a0f 100%); */
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-radius: 0; /* Square style as per theme */
  border: 1px solid #ebeef5;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  font-size: 24px;
  color: #303133;
  margin-bottom: 8px;
}

.login-header p {
  font-size: 14px;
  color: #909399;
}

.login-button {
  width: 100%;
  margin-top: 10px;
  height: 40px;
  font-size: 16px;
}

.login-footer {
  margin-top: 20px;
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
