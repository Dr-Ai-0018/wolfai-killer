<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
    <!-- Login Screen -->
    <div v-if="!isAuthenticated" class="min-h-screen flex items-center justify-center p-6">
      <div class="w-full max-w-md">
        <div class="text-center mb-8">
          <div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-xl shadow-violet-500/30">
            <span class="text-4xl">🔐</span>
          </div>
          <h1 class="text-3xl font-bold text-white mb-2">管理员登录</h1>
          <p class="text-slate-400">请输入管理员密码以访问控制面板</p>
        </div>
        
        <div class="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50 shadow-2xl">
          <div v-if="!adminConfigured" class="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
            <p class="text-amber-400 text-sm flex items-center">
              <span class="mr-2">⚠️</span> 管理员密码未配置，请在后端 .env 文件中设置 WEREWOLF_ADMIN_PASSWORD
            </p>
          </div>
          
          <div class="space-y-5">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">管理员密码</label>
              <input v-model="loginPassword" 
                     type="password"
                     placeholder="请输入密码"
                     @keyup.enter="handleLogin"
                     class="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3.5 text-white
                            focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-all">
            </div>
            
            <button @click="handleLogin" 
                    :disabled="!loginPassword || loginLoading"
                    class="w-full py-3.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 
                           rounded-xl text-white font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed
                           shadow-lg shadow-violet-500/25 flex items-center justify-center gap-2">
              <span v-if="loginLoading" class="animate-spin">⏳</span>
              {{ loginLoading ? '验证中...' : '登录' }}
            </button>
          </div>
          
          <div v-if="loginError" class="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl">
            <p class="text-red-400 text-sm flex items-center"><span class="mr-2">❌</span>{{ loginError }}</p>
          </div>
        </div>
        
        <div class="text-center mt-6">
          <router-link to="/" class="text-slate-500 hover:text-white transition-colors text-sm flex items-center justify-center gap-1">
            <span>←</span> 返回首页
          </router-link>
        </div>
      </div>
    </div>

    <!-- Admin Panel (After Login) -->
    <div v-else class="min-h-screen">
      <!-- Header -->
      <div class="sticky top-0 z-50 bg-slate-950/80 backdrop-blur-xl border-b border-slate-800">
        <div class="max-w-7xl mx-auto px-6 py-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-4">
              <router-link to="/" class="p-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
                </svg>
              </router-link>
              <div>
                <h1 class="text-xl font-bold text-white">控制面板</h1>
                <p class="text-xs text-slate-500">系统配置与模型管理</p>
              </div>
            </div>
            <div class="flex items-center gap-4">
              <div v-if="tokenExpiry" class="text-xs text-slate-500">
                登录有效期至：{{ formatExpiry(tokenExpiry) }}
              </div>
              <button @click="handleLogout" 
                      class="px-4 py-2 bg-slate-800/80 hover:bg-red-600/20 border border-slate-700 hover:border-red-500/50 
                             rounded-xl text-slate-400 hover:text-red-400 text-sm transition-all flex items-center gap-2">
                <span>🚪</span> 退出登录
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="max-w-7xl mx-auto px-6 py-8">
        <div class="grid grid-cols-12 gap-6">
          <!-- API Configuration Card -->
          <div class="col-span-12 lg:col-span-6 bg-slate-800/30 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6 flex items-center">
              <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 flex items-center justify-center mr-3">
                <span class="text-xl">🔑</span>
              </span>
              接口配置
            </h2>
            
            <div class="space-y-5">
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">接口地址</label>
                <input v-model="config.apiUrl" 
                       type="url"
                       placeholder="https://api.openai.com/v1"
                       class="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 text-white
                              focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-all">
              </div>
              
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">接口密钥</label>
                <div class="relative">
                  <input v-model="config.apiKey" 
                         :type="showApiKey ? 'text' : 'password'"
                         placeholder="sk-xxxxxxxx"
                         class="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 pr-12 text-white
                                focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-all">
                  <button @click="showApiKey = !showApiKey"
                          class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors">
                    {{ showApiKey ? '🙈' : '👁️' }}
                  </button>
                </div>
                <p class="mt-2 text-xs text-slate-500">当前: {{ currentConfig.api_key_masked || '未设置' }}</p>
              </div>
              
              <div class="flex gap-3 pt-2">
                <button @click="saveApiConfig" 
                        :disabled="saving"
                        class="flex-1 py-3 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 
                               rounded-xl text-white font-medium transition-all disabled:opacity-50 shadow-lg shadow-violet-500/20">
                  {{ saving ? '保存中...' : '💾 保存配置' }}
                </button>
                <button @click="testConnection" 
                        :disabled="testing"
                        class="flex-1 py-3 bg-slate-700 hover:bg-slate-600 rounded-xl text-white font-medium transition-all">
                  {{ testing ? '测试中...' : '🔗 测试连接' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Fetch Models Card -->
          <div class="col-span-12 lg:col-span-6 bg-slate-800/30 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6 flex items-center">
              <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center mr-3">
                <span class="text-xl">🤖</span>
              </span>
              获取远程模型
            </h2>
            
            <div class="space-y-5">
              <p class="text-slate-400 text-sm">
                从已配置的接口地址获取可用模型编号列表
              </p>
              
              <button @click="fetchRemoteModels" 
                      :disabled="fetching"
                      class="w-full py-3 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 
                             rounded-xl text-white font-medium transition-all disabled:opacity-50 shadow-lg shadow-blue-500/20">
                {{ fetching ? '⏳ 获取中...' : '📥 获取模型编号列表' }}
              </button>
              
              <!-- Fetched Models List -->
              <div v-if="fetchedModels.length > 0" class="space-y-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm text-slate-400">
                    获取到 <span class="text-blue-400 font-bold">{{ fetchedModels.length }}</span> 个模型编号
                  </span>
                  <div class="flex gap-3">
                    <button @click="selectAllModels" class="text-xs text-blue-400 hover:text-blue-300">全选</button>
                    <button @click="selectedFetchedModels = []" class="text-xs text-slate-500 hover:text-slate-300">清空</button>
                  </div>
                </div>
                
                <div class="max-h-48 overflow-y-auto space-y-1 bg-slate-900/50 rounded-xl p-3 border border-slate-700/50">
                  <label v-for="model in fetchedModels" :key="model" 
                         class="flex items-center space-x-3 p-2.5 hover:bg-slate-800/50 rounded-lg cursor-pointer group transition-colors">
                    <input type="checkbox" :value="model" v-model="selectedFetchedModels"
                           class="w-4 h-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500 bg-slate-700">
                    <span class="text-sm text-slate-300 group-hover:text-white truncate flex-1">{{ model }}</span>
                  </label>
                </div>
                
                <button @click="addSelectedModels"
                        :disabled="selectedFetchedModels.length === 0"
                        class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-white text-sm font-medium 
                               transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                  ➕ 添加 {{ selectedFetchedModels.length }} 个模型编号到配置
                </button>
              </div>
            </div>
          </div>

          <!-- Current Models Card -->
          <div class="col-span-12 bg-slate-800/30 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50">
            <div class="flex items-center justify-between mb-6">
              <h2 class="text-lg font-semibold text-white flex items-center">
                <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-green-500/20 flex items-center justify-center mr-3">
                  <span class="text-xl">📋</span>
                </span>
                当前游戏模型编号列表
              </h2>
              <span class="px-3 py-1 bg-slate-700/50 rounded-full text-sm text-slate-400">
                共 {{ currentConfig.model_ids?.length || 0 }} 个模型
              </span>
            </div>
            
            <div class="space-y-5">
              <!-- Model Tags -->
              <div class="flex flex-wrap gap-2 min-h-[80px] bg-slate-900/50 rounded-xl p-4 border border-slate-700/50">
                <div v-for="(model, index) in currentConfig.model_ids" :key="index"
                     class="flex items-center bg-slate-800/80 border border-slate-600/50 rounded-lg px-3 py-2 group hover:border-slate-500 transition-colors">
                  <span class="text-sm text-slate-300">{{ model }}</span>
                  <button @click="removeModel(index)" 
                          class="ml-2 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all">
                    ✕
                  </button>
                </div>
                <div v-if="!currentConfig.model_ids?.length" class="text-slate-500 text-sm flex items-center">
                  <span class="mr-2">📭</span> 暂无模型编号，请从远程获取或手动添加
                </div>
              </div>
              
              <!-- Add Model Input -->
              <div class="flex gap-3">
                <input v-model="newModel" 
                       placeholder="手动添加模型编号..."
                       @keyup.enter="addModel"
                       class="flex-1 bg-slate-900/50 border border-slate-600 rounded-xl px-4 py-3 text-white
                              focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all">
                <button @click="addModel"
                        :disabled="!newModel.trim()"
                        class="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-white font-medium 
                               transition-all disabled:opacity-50">
                  ➕ 添加
                </button>
              </div>
              
              <!-- Save Models -->
              <button @click="saveModels"
                      :disabled="saving"
                      class="w-full py-3 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 
                             rounded-xl text-white font-medium transition-all disabled:opacity-50 shadow-lg shadow-emerald-500/20">
                {{ saving ? '保存中...' : '💾 保存模型编号配置' }}
              </button>
            </div>
          </div>

          <!-- Timeout Configuration Card -->
          <div class="col-span-12 bg-slate-800/30 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50">
            <h2 class="text-lg font-semibold text-white mb-6 flex items-center">
              <span class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 flex items-center justify-center mr-3">
                <span class="text-xl">⏱️</span>
              </span>
              超时配置
            </h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">默认超时时间（秒）</label>
                <input :value="currentConfig.default_timeout" 
                       type="number"
                       disabled
                       class="w-full bg-slate-900/30 border border-slate-700 rounded-xl px-4 py-3 text-slate-400 cursor-not-allowed">
                <p class="mt-2 text-xs text-slate-500">通过后端配置文件修改</p>
              </div>
              
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">模型特定超时</label>
                <div class="bg-slate-900/50 border border-slate-700/50 rounded-xl p-4 max-h-40 overflow-y-auto">
                  <div v-for="(timeout, model) in currentConfig.model_timeout_map" :key="model" 
                       class="flex justify-between text-sm py-2 border-b border-slate-800 last:border-0">
                    <span class="text-slate-400 truncate mr-4">{{ model }}</span>
                    <span class="text-amber-400 font-medium">{{ timeout }}s</span>
                  </div>
                  <div v-if="!Object.keys(currentConfig.model_timeout_map || {}).length" class="text-slate-500 text-sm">
                    无特定配置
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast Notification -->
    <transition name="toast">
      <div v-if="toast.show" 
           :class="['fixed bottom-6 right-6 px-6 py-3 rounded-xl text-white shadow-xl z-50',
                    toast.type === 'success' ? 'bg-green-600' : 
                    toast.type === 'error' ? 'bg-red-600' : 'bg-blue-600']">
        {{ toast.message }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { adminApi } from '@/api'

// Auth State
const isAuthenticated = ref(false)
const adminConfigured = ref(true)
const loginPassword = ref('')
const loginLoading = ref(false)
const loginError = ref('')
const tokenExpiry = ref(null)

// Config State
const currentConfig = ref({
  api_url: '',
  api_key_masked: '',
  models: [],
  model_ids: [],
  default_timeout: 60,
  model_timeout_map: {}
})

const config = reactive({
  apiUrl: '',
  apiKey: ''
})

const showApiKey = ref(false)
const saving = ref(false)
const testing = ref(false)
const fetching = ref(false)
const fetchedModels = ref([])
const selectedFetchedModels = ref([])
const newModel = ref('')

const toast = reactive({
  show: false,
  message: '',
  type: 'info'
})

// Methods
const showToast = (message, type = 'info') => {
  toast.message = message
  toast.type = type
  toast.show = true
  setTimeout(() => { toast.show = false }, 3000)
}

const formatExpiry = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { 
    month: 'short', 
    day: 'numeric', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

const checkAdminStatus = async () => {
  try {
    const res = await adminApi.checkStatus()
    adminConfigured.value = res.data.configured
    
    // Check if already logged in (token exists and valid)
    if (adminApi.isTokenValid()) {
      try {
        await adminApi.verify()
        isAuthenticated.value = true
        tokenExpiry.value = localStorage.getItem('werewolf_admin_token_expiry')
        await loadConfig()
      } catch {
        // Token invalid, clear it
        adminApi.clearToken()
      }
    }
  } catch (error) {
    console.error('检查管理状态失败：', error)
  }
}

const handleLogin = async () => {
  if (!loginPassword.value) return
  
  loginLoading.value = true
  loginError.value = ''
  
  try {
    const res = await adminApi.login(loginPassword.value)
    if (res.data.success) {
      isAuthenticated.value = true
      tokenExpiry.value = res.data.expires_at
      loginPassword.value = ''
      await loadConfig()
      showToast('登录成功', 'success')
    }
  } catch (error) {
    loginError.value = error.response?.data?.detail || '登录失败'
  } finally {
    loginLoading.value = false
  }
}

const handleLogout = async () => {
  await adminApi.logout()
  isAuthenticated.value = false
  tokenExpiry.value = null
  loginPassword.value = ''
  showToast('已退出登录', 'info')
}

const loadConfig = async () => {
  try {
    const res = await adminApi.getConfig()
    currentConfig.value = {
      ...res.data,
      model_ids: res.data.model_ids || res.data.models || []
    }
    config.apiUrl = res.data.api_url || ''
  } catch (error) {
    if (error.response?.status === 401) {
      // Token expired
      handleLogout()
      showToast('登录已过期，请重新登录', 'error')
    } else {
      showToast('加载配置失败', 'error')
    }
  }
}

const saveApiConfig = async () => {
  saving.value = true
  try {
    const updates = {}
    if (config.apiUrl) updates.api_url = config.apiUrl
    if (config.apiKey) updates.api_key = config.apiKey
    
    await adminApi.updateConfig(updates)
    await loadConfig()
    config.apiKey = ''
    showToast('接口配置已保存', 'success')
  } catch (error) {
    if (error.response?.status === 401) {
      handleLogout()
      showToast('登录已过期，请重新登录', 'error')
    } else {
      showToast('保存失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  } finally {
    saving.value = false
  }
}

const testConnection = async () => {
  testing.value = true
  try {
    const apiUrl = config.apiUrl || currentConfig.value.api_url
    const apiKey = config.apiKey || 'use_existing'
    
    if (!apiUrl) {
      showToast('请先配置API地址', 'error')
      return
    }
    
    const res = await adminApi.fetchModels(apiUrl, apiKey)
    if (res.data.success) {
      showToast(`连接成功！获取到 ${res.data.total} 个模型编号`, 'success')
    } else {
      showToast('连接失败: ' + res.data.message, 'error')
    }
  } catch (error) {
    if (error.response?.status === 401) {
      handleLogout()
      showToast('登录已过期，请重新登录', 'error')
    } else {
      showToast('连接失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  } finally {
    testing.value = false
  }
}

const fetchRemoteModels = async () => {
  fetching.value = true
  try {
    const apiUrl = config.apiUrl || currentConfig.value.api_url
    const apiKey = config.apiKey || 'use_existing'
    
    if (!apiUrl) {
      showToast('请先配置API地址', 'error')
      fetching.value = false
      return
    }
    
    const res = await adminApi.fetchModels(apiUrl, apiKey)
    if (res.data.success) {
      fetchedModels.value = res.data.model_ids || res.data.models || []
      selectedFetchedModels.value = []
      showToast(`获取到 ${res.data.total} 个模型编号`, 'success')
    } else {
      showToast('获取失败: ' + res.data.message, 'error')
    }
  } catch (error) {
    if (error.response?.status === 401) {
      handleLogout()
      showToast('登录已过期，请重新登录', 'error')
    } else {
      showToast('获取失败: ' + (error.response?.data?.detail || error.message), 'error')
    }
  } finally {
    fetching.value = false
  }
}

const selectAllModels = () => {
  selectedFetchedModels.value = [...fetchedModels.value]
}

const addSelectedModels = async () => {
  const existingModels = new Set(currentConfig.value.model_ids || [])
  const newModels = selectedFetchedModels.value.filter(m => !existingModels.has(m))
  
  if (newModels.length === 0) {
    showToast('所选模型已存在', 'info')
    return
  }
  
  currentConfig.value.model_ids = [...(currentConfig.value.model_ids || []), ...newModels]
  await saveModels()
  selectedFetchedModels.value = []
}

const addModel = () => {
  const model = newModel.value.trim()
  if (!model) return
  
  if (currentConfig.value.model_ids?.includes(model)) {
    showToast('模型已存在', 'info')
    return
  }
  
  currentConfig.value.model_ids = [...(currentConfig.value.model_ids || []), model]
  newModel.value = ''
}

const removeModel = (index) => {
  currentConfig.value.model_ids.splice(index, 1)
}

const saveModels = async () => {
  saving.value = true
  try {
    await adminApi.updateConfig({ model_ids: currentConfig.value.model_ids })
    showToast('模型编号配置已保存', 'success')
  } catch (error) {
    if (error.response?.status === 401) {
      handleLogout()
      showToast('登录已过期，请重新登录', 'error')
    } else {
      showToast('保存失败', 'error')
    }
  } finally {
    saving.value = false
  }
}

// Lifecycle
onMounted(() => {
  checkAdminStatus()
})
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
