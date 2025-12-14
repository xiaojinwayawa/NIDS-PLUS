import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSystemStore = defineStore('system', () => {
  const isAuthenticated = ref(false)
  const systemState = ref<'idle' | 'running' | 'stopped'>('idle')

  function setAuthenticated(value: boolean) {
    isAuthenticated.value = value
  }

  function setSystemState(state: 'idle' | 'running' | 'stopped') {
    systemState.value = state
  }

  return {
    isAuthenticated,
    systemState,
    setAuthenticated,
    setSystemState
  }
})
