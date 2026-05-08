<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>NIDS 系统</h1>
        <p>网络入侵检测系统</p>
      </div>
      
      <el-tabs v-model="activeTab" class="auth-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form 
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            label-position="top"
            class="login-form"
            @keyup.enter="handleLogin"
          >
            <el-form-item label="用户名" prop="username">
              <el-input 
                v-model="loginForm.username" 
                placeholder="请输入用户名"
                :prefix-icon="User"
              />
            </el-form-item>
            
            <el-form-item label="密码" prop="password">
              <el-input 
                v-model="loginForm.password" 
                type="password" 
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>

            <el-form-item label="验证码" prop="captcha_code">
              <div class="captcha-container">
                <el-input 
                  v-model="loginForm.captcha_code" 
                  placeholder="请输入4位验证码"
                  class="captcha-input"
                />
                <div class="captcha-image" @click="fetchCaptcha">
                  <img v-if="captchaImage" :src="captchaImage" alt="captcha" />
                  <span v-else class="captcha-loading">加载中...</span>
                </div>
              </div>
            </el-form-item>
            
            <el-form-item>
              <el-button 
                type="primary" 
                class="login-button" 
                :loading="loading"
                @click="handleLogin"
              >
                登录
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form 
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            label-position="top"
            class="login-form"
            @keyup.enter="handleRegister"
          >
            <el-form-item label="用户名" prop="username">
              <el-input 
                v-model="registerForm.username" 
                placeholder="请输入用户名"
                :prefix-icon="User"
              />
            </el-form-item>
            
            <el-form-item label="密码" prop="password">
              <el-input 
                v-model="registerForm.password" 
                type="password" 
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>

            <el-form-item label="邮箱 (选填)" prop="email">
              <el-input 
                v-model="registerForm.email" 
                placeholder="请输入邮箱"
                :prefix-icon="Message"
              />
            </el-form-item>

            <el-form-item label="验证码" prop="captcha_code">
              <div class="captcha-container">
                <el-input 
                  v-model="registerForm.captcha_code" 
                  placeholder="请输入4位验证码"
                  class="captcha-input"
                />
                <div class="captcha-image" @click="fetchCaptcha">
                  <img v-if="captchaImage" :src="captchaImage" alt="captcha" />
                  <span v-else class="captcha-loading">加载中...</span>
                </div>
              </div>
            </el-form-item>
            
            <el-form-item>
              <el-button 
                type="success" 
                class="login-button" 
                :loading="loading"
                @click="handleRegister"
              >
                注册新账号
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useSystemStore } from '@/stores/system'
import api from '@/api'

const router = useRouter()
const systemStore = useSystemStore()
const activeTab = ref('login')

const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()
const loading = ref(false)

// Captcha state
const currentCaptchaId = ref('')
const captchaImage = ref('')

const fetchCaptcha = async () => {
  try {
    const res = await api.get('/auth/captcha')
    currentCaptchaId.value = res.data.captcha_id
    captchaImage.value = res.data.captcha_image_base64
  } catch (error) {
    ElMessage.error('获取验证码失败')
  }
}

onMounted(() => {
  fetchCaptcha()
})

const loginForm = reactive({
  username: '',
  password: '',
  captcha_code: ''
})

const registerForm = reactive({
  username: '',
  password: '',
  email: '',
  captcha_code: ''
})

const loginRules = reactive<FormRules>({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
})

const registerRules = reactive<FormRules>({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
})

const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await systemStore.login({
          username: loginForm.username, 
          password: loginForm.password,
          captcha_id: currentCaptchaId.value,
          captcha_code: loginForm.captcha_code
        })
        ElMessage.success('登录成功')
        router.push('/')
      } catch (error: any) {
        ElMessage.error(error.response?.data?.detail || '登录失败')
        // Refresh captcha on failure
        fetchCaptcha()
        loginForm.captcha_code = ''
      } finally {
        loading.value = false
      }
    }
  })
}

const handleRegister = async () => {
  if (!registerFormRef.value) return
  
  await registerFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await api.post('/auth/register', {
          username: registerForm.username,
          password: registerForm.password,
          email: registerForm.email,
          captcha_id: currentCaptchaId.value,
          captcha_code: registerForm.captcha_code
        })
        ElMessage.success('注册成功，请切换到登录页进行登录')
        activeTab.value = 'login'
        // Reset forms
        registerForm.username = ''
        registerForm.password = ''
        registerForm.email = ''
        registerForm.captcha_code = ''
        fetchCaptcha()
      } catch (error: any) {
        ElMessage.error(error.response?.data?.detail || '注册失败')
        fetchCaptcha()
        registerForm.captcha_code = ''
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
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border-radius: 0;
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

.captcha-container {
  display: flex;
  align-items: center;
  gap: 12px;
}

.captcha-input {
  flex: 1;
}

.captcha-image {
  width: 120px;
  height: 40px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f7fa;
}

.captcha-image img {
  width: 100%;
  height: 100%;
}

.captcha-loading {
  font-size: 12px;
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

@media (max-width: 1100px) {
  .login-container {
    padding: 0 20px;
  }
}
</style>
