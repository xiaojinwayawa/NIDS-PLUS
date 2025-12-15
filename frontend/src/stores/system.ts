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

  async function login(username: string, password: string) {
    const response = await api.post('/auth/login', { username, password })
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
    const wsUrl = `${protocol}//${host}/ws`
    
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
        recentAlerts.value.unshift(alert)
        if (recentAlerts.value.length > 20) {
          recentAlerts.value.pop()
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
  async function startSystem(mode: string = 'pcap', source?: string) {
    await api.post('/system/start', { mode, source })
    // State update usually comes via WS, but we can optimistically set it or wait
  }
  
  async function stopSystem() {
    await api.post('/system/stop')
  }

  return {
    isAuthenticated,
    user,
    systemState,
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
    stopSystem
  }
})
