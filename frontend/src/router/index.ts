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
          path: 'copilot',
          name: 'copilot',
          component: () => import('../views/CopilotView.vue')
        },
        {
          path: 'training',
          name: 'training',
          component: () => import('../views/TrainingView.vue')
        },
        {
          path: 'experiments',
          name: 'experiments',
          component: () => import('../views/ExperimentsView.vue')
        },
        {
          path: 'model-evaluation',
          name: 'model-evaluation',
          component: () => import('../views/ModelEvaluationView.vue')
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
          path: 'users',
          name: 'users',
          component: () => import('../views/UsersView.vue')
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
  const hasToken = !!localStorage.getItem('token')

  if (systemStore.isAuthenticated !== hasToken) {
    systemStore.setAuthenticated(hasToken)
  }
  
  if (to.meta.requiresAuth && !hasToken) {
    next('/login')
  } else if (to.path === '/login' && hasToken) {
    next('/')
  } else {
    next()
  }
})

window.addEventListener('app:unauthorized', async () => {
  const systemStore = useSystemStore()
  systemStore.setAuthenticated(false)
  systemStore.disconnectWebSocket()

  if (router.currentRoute.value.path !== '/login') {
    await router.replace('/login')
  }
})

export default router
