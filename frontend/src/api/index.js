import axios from 'axios'

const API_BASE = 'http://localhost:8000'
const WS_BASE = 'ws://localhost:8000'

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  timeout: 30000,
})

// Config API
export const configApi = {
  getRoles: () => api.get('/config/roles'),
  getPersonalities: () => api.get('/config/personalities'),
  getModels: () => api.get('/config/models'),
}

// Game API
export const gameApi = {
  create: (config) => api.post('/game/create', config),
  getStatus: (gameId) => api.get(`/game/${gameId}/status`),
  getPlayers: (gameId) => api.get(`/game/${gameId}/players`),
  getPlayerView: (gameId, seat) => api.get(`/game/${gameId}/player/${seat}`),
  getLog: (gameId, offset = 0, limit = 100) => api.get(`/game/${gameId}/log`, { params: { offset, limit } }),
  start: (gameId) => api.post(`/game/${gameId}/start`),
  pause: (gameId) => api.post(`/game/${gameId}/pause`),
  resume: (gameId) => api.post(`/game/${gameId}/resume`),
  submitAction: (gameId, actionType, data) => api.post(`/game/${gameId}/action`, { action_type: actionType, data }),
  
  // 上帝模式 API
  verifyGodMode: (gameId, password) => api.post(`/game/${gameId}/god-mode/verify`, { password }),
  getGodModeLogs: (gameId, password, offset = 0, limit = 100) => 
    api.get(`/game/${gameId}/god-mode/logs`, { params: { password, offset, limit } }),
  getGodModePlayers: (gameId, password) => 
    api.get(`/game/${gameId}/god-mode/players`, { params: { password } }),
  
  // 冥界复盘 API
  getPhantomActions: (gameId) => api.get(`/game/${gameId}/phantom-actions`),
}

// Admin API with JWT Authentication
const TOKEN_KEY = 'werewolf_admin_token'
const TOKEN_EXPIRY_KEY = 'werewolf_admin_token_expiry'

// Get stored token
const getToken = () => localStorage.getItem(TOKEN_KEY)
const getTokenExpiry = () => localStorage.getItem(TOKEN_EXPIRY_KEY)

// Store token
const setToken = (token, expiresAt) => {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(TOKEN_EXPIRY_KEY, expiresAt)
}

// Clear token
const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_EXPIRY_KEY)
}

// Check if token is valid
const isTokenValid = () => {
  const token = getToken()
  const expiry = getTokenExpiry()
  if (!token || !expiry) return false
  return new Date(expiry) > new Date()
}

// Get auth header
const getAuthHeader = () => {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const adminApi = {
  // Token management
  getToken,
  setToken,
  clearToken,
  isTokenValid,
  
  // Check if admin is configured
  checkStatus: () => api.get('/admin/check'),
  
  // Login and get JWT token
  login: async (password) => {
    const res = await api.post('/admin/login', { password })
    if (res.data.success && res.data.access_token) {
      setToken(res.data.access_token, res.data.expires_at)
    }
    return res
  },
  
  // Logout
  logout: () => {
    clearToken()
    return Promise.resolve({ data: { success: true } })
  },
  
  // Verify current token
  verify: () => api.get('/admin/verify', { headers: getAuthHeader() }),
  
  // Refresh token
  refresh: async () => {
    const res = await api.post('/admin/refresh', {}, { headers: getAuthHeader() })
    if (res.data.success && res.data.access_token) {
      setToken(res.data.access_token, res.data.expires_at)
    }
    return res
  },
  
  // Get config (requires auth)
  getConfig: () => api.get('/admin/config', { headers: getAuthHeader() }),
  
  // Update config (requires auth)
  updateConfig: (config) => api.post('/admin/config', config, { headers: getAuthHeader() }),
  
  // Fetch remote models (requires auth)
  fetchModels: (apiUrl, apiKey) => api.post('/admin/fetch-models', 
    { api_url: apiUrl, api_key: apiKey }, 
    { headers: getAuthHeader() }
  ),
}

// Stats API
export const statsApi = {
  getOverview: () => api.get('/stats/overview'),
  getDetailed: () => api.get('/stats/detailed'),
  getRoleStats: () => api.get('/stats/roles'),
  getPersonalityStats: () => api.get('/stats/personalities'),
  getModelStats: () => api.get('/stats/models'),
  getHistory: (page = 1, perPage = 20) => api.get('/stats/history', { params: { page, per_page: perPage } }),
  getGameDetail: (gameId) => api.get(`/stats/game/${gameId}`),
}

// WebSocket connection class
export class GameWebSocket {
  constructor(gameId, seat, callbacks = {}) {
    this.gameId = gameId
    this.seat = seat
    this.callbacks = callbacks
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  connect() {
    const url = `${WS_BASE}/ws/${this.gameId}/${this.seat}`
    console.log('Connecting to WebSocket:', url)
    
    this.ws = new WebSocket(url)
    
    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
      if (this.callbacks.onConnect) {
        this.callbacks.onConnect()
      }
    }
    
    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        console.log('WS message:', message)
        
        if (this.callbacks.onMessage) {
          this.callbacks.onMessage(message)
        }
        
        // Handle specific events
        if (message.event === 'state' && this.callbacks.onState) {
          this.callbacks.onState(message.data)
        }
        if (message.event === 'action_required' && this.callbacks.onActionRequired) {
          this.callbacks.onActionRequired(message.data)
        }
        if (message.event === 'connected' && this.callbacks.onConnected) {
          this.callbacks.onConnected(message.data)
        }
        if (message.event === 'your_role' && this.callbacks.onRole) {
          this.callbacks.onRole(message.data)
        }
        if (message.event === 'seer_result' && this.callbacks.onSeerResult) {
          this.callbacks.onSeerResult(message.data)
        }
      } catch (e) {
        console.error('Failed to parse WS message:', e)
      }
    }
    
    this.ws.onclose = () => {
      console.log('WebSocket closed')
      if (this.callbacks.onDisconnect) {
        this.callbacks.onDisconnect()
      }
      
      // Auto reconnect
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++
        console.log(`Reconnecting... attempt ${this.reconnectAttempts}`)
        setTimeout(() => this.connect(), 2000)
      }
    }
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      if (this.callbacks.onError) {
        this.callbacks.onError(error)
      }
    }
  }
  
  sendAction(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'action', data }))
    }
  }
  
  ping() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'ping' }))
    }
  }
  
  close() {
    this.maxReconnectAttempts = 0  // Prevent reconnect
    if (this.ws) {
      this.ws.close()
    }
  }
}

// Avatar URL helper
export const getAvatarUrl = (avatar) => {
  if (!avatar) return null
  return `${API_BASE}/emojis/${avatar}`
}

export default api
