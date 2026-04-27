import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'

interface User {
  username: string
  user_id: number
  role: string
}

interface Alert {
  id?: number
  timestamp: string
  src_ip: string
  dst_ip: string
  protocol: string
  attack_type: string
  confidence: number
  severity: string
  first_seen?: string
  last_seen?: string
  repeat_count?: number
  event_status?: string
  duration_seconds?: number
  event_action?: string
}

interface TrafficStats {
  timestamp: number
  throughput: number // packets/sec
  latency: number // ms
}

export const useSystemStore = defineStore('system', () => {
  const isAuthenticated = ref(!!localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const systemState = ref<'idle' | 'running' | 'stopped' | 'error'>('idle')
  
  // System configuration (saved for resume)
  const savedConfig = ref<{ mode: string; source?: string; models?: string[] } | null>(null)
  
  // Load saved config from localStorage on initialization
  try {
    const saved = localStorage.getItem('systemConfig')
    if (saved) {
      savedConfig.value = JSON.parse(saved)
      console.log('Loaded saved system config:', savedConfig.value)
    }
  } catch (e) {
    console.error('Failed to load system config from localStorage', e)
  }
  
  // Real-time data
  const trafficHistory = ref<TrafficStats[]>([])
  const recentAlerts = ref<Alert[]>([])
  const currentThroughput = ref(0)
  const currentLatency = ref(0)
  const threatLevel = ref<'Low' | 'Medium' | 'High'>('Low')
  
  // WebSocket
  let ws: WebSocket | null = null

  function setAuthenticated(value: boolean) {
    isAuthenticated.value = value
  }

  function setSystemState(state: 'idle' | 'running' | 'stopped' | 'error') {
    systemState.value = state
  }

  async function login(data: { username: string; password: string; captcha_id?: string; captcha_code?: string }) {
    const response = await api.post('/auth/login', data)
    const { access_token } = response.data
    
    localStorage.setItem('token', access_token)
    isAuthenticated.value = true
    
    // Fetch user info
    await fetchUserInfo()
  }

  async function logout() {
    try {
        await api.post('/auth/logout')
    } catch (e) {
        // Ignore error on logout
    }
    localStorage.removeItem('token')
    isAuthenticated.value = false
    user.value = null
    disconnectWebSocket()
  }

  async function fetchUserInfo() {
    try {
      const response = await api.get('/auth/me')
      user.value = response.data
    } catch (e) {
      console.error("Failed to fetch user info")
    }
  }
  
  // WebSocket Management
  function connectWebSocket() {
    if (ws && ws.readyState === WebSocket.OPEN) return

    // Use relative path for proxy to handle
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    
    // Add JWT token for authentication
    const token = localStorage.getItem('token')
    const wsUrl = token 
      ? `${protocol}//${host}/ws?token=${encodeURIComponent(token)}`
      : `${protocol}//${host}/ws`
    
    ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('WebSocket connected')
    }
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        handleWebSocketMessage(message)
      } catch (e) {
        console.error('Failed to parse WS message', e)
      }
    }
    
    ws.onclose = () => {
      console.log('WebSocket disconnected')
      // Optional: Auto reconnect logic could go here
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error', error)
    }
  }
  
  function disconnectWebSocket() {
    if (ws) {
      ws.close()
      ws = null
    }
  }
  
  function handleWebSocketMessage(message: any) {
    switch (message.type) {
      case 'status':
        systemState.value = message.data.state.toLowerCase()
        break
      case 'stats':
        // Assuming message.data contains { timestamp, throughput, latency }
        // Adjust based on actual backend structure
        const stats: TrafficStats = {
          timestamp: Date.now(),
          throughput: message.data.throughput || 0,
          latency: message.data.latency || 0
        }
        currentThroughput.value = stats.throughput
        currentLatency.value = stats.latency
        
        // Keep history limited to last 60 points (e.g., 1 minute if 1 sec interval)
        trafficHistory.value.push(stats)
        if (trafficHistory.value.length > 60) {
          trafficHistory.value.shift()
        }
        break
      case 'alert':
        const alert: Alert = message.data
        if (alert.id != null) {
          const existingIndex = recentAlerts.value.findIndex(a => a.id === alert.id)
          if (existingIndex >= 0) {
            const existingAlert = recentAlerts.value[existingIndex]
            const mergedRepeatCount = alert.repeat_count ?? existingAlert.repeat_count ?? 1
            recentAlerts.value[existingIndex] = {
              ...existingAlert,
              ...alert,
              repeat_count: mergedRepeatCount
            }
            const [updatedAlert] = recentAlerts.value.splice(existingIndex, 1)
            recentAlerts.value.unshift(updatedAlert)
          } else {
            recentAlerts.value.unshift({
              ...alert,
              repeat_count: alert.repeat_count ?? 1
            })
          }
        } else {
          recentAlerts.value.unshift({
            ...alert,
            repeat_count: alert.repeat_count ?? 1
          })
        }
        if (recentAlerts.value.length > 20) {
          recentAlerts.value.length = 20
        }
        updateThreatLevel()
        break
    }
  }
  
  function updateThreatLevel() {
    // Simple logic: High if any high severity alert in recent list
    const hasHigh = recentAlerts.value.some(a => a.severity === 'high' || a.severity === 'critical')
    const hasMedium = recentAlerts.value.some(a => a.severity === 'medium')
    
    if (hasHigh) threatLevel.value = 'High'
    else if (hasMedium) threatLevel.value = 'Medium'
    else threatLevel.value = 'Low'
  }
  
  // System Control Actions
  async function startSystem(mode: string = 'pcap', source?: string, models?: string[]) {
    await api.post('/system/start', { mode, source })
    // Save configuration for resume (both in memory and localStorage)
    savedConfig.value = { mode, source, models }
    localStorage.setItem('systemConfig', JSON.stringify(savedConfig.value))
    console.log('Saved system config:', savedConfig.value)
    // State update usually comes via WS, but we can optimistically set it or wait
  }
  
  async function stopSystem() {
    await api.post('/system/stop')
  }
  
  async function resumeSystem() {
    // Resume with saved configuration
    if (savedConfig.value) {
      await startSystem(savedConfig.value.mode, savedConfig.value.source, savedConfig.value.models)
      return true
    }
    return false
  }
  
  function clearSavedConfig() {
    savedConfig.value = null
    localStorage.removeItem('systemConfig')
    console.log('Cleared saved system config')
  }
  
  async function fetchSystemStatus() {
    try {
      const response = await api.get('/system/status')
      const state = response.data.state?.toLowerCase()
      if (state && ['idle', 'running', 'stopped', 'error'].includes(state)) {
        systemState.value = state as 'idle' | 'running' | 'stopped' | 'error'
      }
      return response.data
    } catch (e) {
      console.error("Failed to fetch system status", e)
      return null
    }
  }

  return {
    isAuthenticated,
    user,
    systemState,
    savedConfig,
    trafficHistory,
    recentAlerts,
    currentThroughput,
    currentLatency,
    threatLevel,
    setAuthenticated,
    setSystemState,
    login,
    logout,
    fetchUserInfo,
    connectWebSocket,
    disconnectWebSocket,
    startSystem,
    stopSystem,
    resumeSystem,
    clearSavedConfig,
    fetchSystemStatus
  }
})
