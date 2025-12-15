import { createRouter, createWebHistory } from 'vue-router'
import { useSystemStore } from '@/stores/system'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      component: () => import('../layout/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('../views/DashboardView.vue')
        },
        {
          path: 'traffic',
          name: 'traffic',
          component: () => import('../views/TrafficAnalysisView.vue')
        },
        {
          path: 'alerts',
          name: 'alerts',
          component: () => import('../views/AlertsView.vue')
        },
        {
          path: 'attacks',
          name: 'attacks',
          component: () => import('../views/AttacksView.vue')
        },
        {
          path: 'training',
          name: 'training',
          component: () => import('../views/TrainingView.vue')
        },
        {
          path: 'performance',
          name: 'performance',
          component: () => import('../views/PerformanceView.vue')
        },
        {
          path: 'datasets',
          name: 'datasets',
          component: () => import('../views/DatasetsView.vue')
        },
        {
          path: 'logs',
          name: 'logs',
          component: () => import('../views/LogsView.vue')
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('../views/SettingsView.vue')
        }
      ]
    }
  ]
})

router.beforeEach((to, from, next) => {
  const systemStore = useSystemStore()
  const isAuthenticated = systemStore.isAuthenticated
  
  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
