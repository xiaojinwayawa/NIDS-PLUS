<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="aside">
      <div class="logo">
        <h2>NIDS System</h2>
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
          <span>Dashboard</span>
        </el-menu-item>
        
        <el-menu-item index="/traffic">
          <el-icon><Monitor /></el-icon>
          <span>Traffic Analysis</span>
        </el-menu-item>
        
        <el-menu-item index="/alerts">
          <el-icon><Warning /></el-icon>
          <span>Alerts</span>
        </el-menu-item>
        
        <el-menu-item index="/attacks">
          <el-icon><PieChart /></el-icon>
          <span>Attack Stats</span>
        </el-menu-item>
        
        <el-sub-menu index="model">
          <template #title>
            <el-icon><Cpu /></el-icon>
            <span>Model Management</span>
          </template>
          <el-menu-item index="/training">Training</el-menu-item>
          <el-menu-item index="/experiments">Experiments</el-menu-item>
          <el-menu-item index="/performance">Performance</el-menu-item>
          <el-menu-item index="/datasets">Datasets</el-menu-item>
        </el-sub-menu>
        
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>System Logs</span>
        </el-menu-item>
        
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>Settings</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <!-- Breadcrumb could go here -->
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              Admin <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">Logout</el-dropdown-item>
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
  Odometer, Monitor, Warning, PieChart, Cpu, Document, Setting, ArrowDown 
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
}

.aside {
  background-color: #304156;
  color: #bfcbd9;
  transition: width 0.3s;
  overflow-x: hidden;
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  background-color: #2b2f3a;
  color: #fff;
  font-weight: 600;
}

.el-menu-vertical {
  border-right: none;
}

.header {
  height: 60px;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.main {
  background-color: #f0f2f5;
  padding: 20px;
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
