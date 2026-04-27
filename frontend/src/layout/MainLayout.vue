<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="aside">
      <div class="logo">
        <h2>NIDS 系统</h2>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <span>仪表板</span>
        </el-menu-item>
        
        <el-menu-item index="/traffic">
          <el-icon><Monitor /></el-icon>
          <span>流量分析</span>
        </el-menu-item>
        
        <el-menu-item index="/alerts">
          <el-icon><Warning /></el-icon>
          <span>告警</span>
        </el-menu-item>
        
        <el-menu-item index="/attacks">
          <el-icon><PieChart /></el-icon>
          <span>攻击统计</span>
        </el-menu-item>
        
        <el-sub-menu index="model">
          <template #title>
            <el-icon><Cpu /></el-icon>
            <span>模型管理</span>
          </template>
          <el-menu-item index="/training">模型训练</el-menu-item>
          <el-menu-item index="/experiments">实验</el-menu-item>
          <el-menu-item index="/model-evaluation">总体模型评估</el-menu-item>
          <el-menu-item index="/datasets">数据集</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/copilot">
          <el-icon><Star /></el-icon>
          <span>智能辅助</span>
        </el-menu-item>
        
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>系统日志</span>
        </el-menu-item>
        
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>设置</span>
        </el-menu-item>

        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container class="content-container">
      <el-header class="header">
        <div class="header-left">
          <!-- Breadcrumb could go here -->
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              {{ systemStore.user?.username || '用户' }} <el-tag v-if="systemStore.user?.role === 'admin'" size="small" type="danger" style="margin: 0 5px;">超管</el-tag> <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSystemStore } from '@/stores/system'
import { 
  Odometer, Monitor, Warning, PieChart, Cpu, Document, Setting, ArrowDown, Star, User 
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const systemStore = useSystemStore()

const activeMenu = computed(() => route.path)

const handleCommand = async (command: string) => {
  if (command === 'logout') {
    await systemStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  overflow: hidden;
}

.aside {
  background-color: #304156;
  color: #bfcbd9;
  transition: width 0.3s;
  overflow-x: hidden;
  flex-shrink: 0;
  position: relative;
  z-index: 30;
}

.content-container {
  min-width: 0;
  overflow: hidden;
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  background-color: #2b2f3a;
  color: #fff;
  font-weight: 600;
  font-size: 20px;
}

.el-menu-vertical {
  border-right: none;
  font-size: 16px;
}

.el-menu-vertical :deep(.el-menu-item),
.el-menu-vertical :deep(.el-sub-menu__title) {
  font-size: 16px;
  height: 56px;
  line-height: 56px;
}

.header {
  height: 60px;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  position: relative;
  z-index: 20;
}

.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.main {
  background-color: #f0f2f5;
  padding: 20px;
  min-width: 0;
  overflow: auto;
  position: relative;
  z-index: 1;
}

/* Transition */
.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.3s;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
