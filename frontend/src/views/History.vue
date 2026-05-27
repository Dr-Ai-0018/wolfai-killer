<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-6xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-8">历史记录与统计</h1>
      
      <!-- Tab Navigation -->
      <div class="flex space-x-4 mb-8">
        <button v-for="tab in tabs" :key="tab.key"
                @click="activeTab = tab.key"
                :class="[
                  'px-6 py-3 rounded-xl font-medium transition-colors',
                  activeTab === tab.key 
                    ? 'bg-game-accent text-white' 
                    : 'glass text-gray-400 hover:text-white'
                ]">
          {{ tab.icon }} {{ tab.name }}
        </button>
      </div>
      
      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'">
        <!-- Main Stats -->
        <div class="grid md:grid-cols-4 gap-4 mb-8">
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-game-accent-light">{{ stats.total_games || 0 }}</div>
            <div class="text-gray-400">总对局数</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-game-accent-light">{{ stats.total_rounds || 0 }}</div>
            <div class="text-gray-400">总回合数</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-wolf-red">{{ formatPercent(stats.wolf_win_rate) }}</div>
            <div class="text-gray-400">狼人胜率</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-good-green">{{ formatPercent(stats.good_win_rate) }}</div>
            <div class="text-gray-400">好人胜率</div>
          </div>
        </div>
        
        <!-- Additional Stats -->
        <div class="grid md:grid-cols-3 gap-4 mb-8">
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-3xl font-bold text-purple-400">{{ stats.wolf_wins || 0 }}</div>
            <div class="text-gray-400">狼人获胜场次</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-3xl font-bold text-blue-400">{{ stats.good_wins || 0 }}</div>
            <div class="text-gray-400">好人获胜场次</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-3xl font-bold text-yellow-400">{{ formatAvgDuration(stats.avg_duration) }}</div>
            <div class="text-gray-400">平均对局时长</div>
          </div>
        </div>
      </div>
      
      <!-- Role Stats Tab -->
      <div v-if="activeTab === 'roles'">
        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="(stat, role) in roleStats" :key="role" 
               class="glass rounded-xl p-6">
            <div class="flex items-center mb-4">
              <span class="text-3xl mr-3">{{ getRoleIcon(role) }}</span>
              <div>
                <h3 class="text-xl font-bold text-white">{{ role }}</h3>
                <p class="text-sm text-gray-400">{{ stat.games }} 场对局</p>
              </div>
            </div>
            <div class="space-y-3">
              <div class="flex justify-between">
                <span class="text-gray-400">胜率</span>
                <span class="text-game-accent-light font-bold">{{ formatPercent(stat.win_rate) }}</span>
              </div>
              <div class="w-full bg-game-dark rounded-full h-2">
                <div class="bg-game-accent h-2 rounded-full" :style="{width: formatPercent(stat.win_rate)}"></div>
              </div>
              <div class="flex justify-between text-sm">
                <span class="text-gray-500">获胜 {{ stat.wins }} 场</span>
                <span class="text-gray-500">死亡 {{ stat.deaths }} 次</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Personality Stats Tab -->
      <div v-if="activeTab === 'personalities'">
        <div v-if="Object.keys(personalityStats).length === 0" class="glass rounded-xl p-8 text-center text-gray-400">
          暂无人格统计数据
        </div>
        <div v-else class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="(stat, name) in personalityStats" :key="name" 
               class="glass rounded-xl p-6">
            <h3 class="text-lg font-bold text-game-accent-light mb-2">{{ name }}</h3>
            <p class="text-sm text-gray-400 mb-4">{{ stat.games }} 场对局</p>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-400">总胜率</span>
                <span class="text-white">{{ formatPercent(stat.win_rate) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-wolf-red">狼人胜率</span>
                <span class="text-white">{{ formatPercent(stat.wolf_win_rate) }} ({{ stat.wolf_games }}场)</span>
              </div>
              <div class="flex justify-between">
                <span class="text-good-green">好人胜率</span>
                <span class="text-white">{{ formatPercent(stat.good_win_rate) }} ({{ stat.good_games }}场)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Model Stats Tab -->
      <div v-if="activeTab === 'models'">
        <div v-if="Object.keys(modelStats).length === 0" class="glass rounded-xl p-8 text-center text-gray-400">
          暂无模型统计数据
        </div>
        <div v-else class="grid md:grid-cols-2 gap-4">
          <div v-for="(stat, name) in modelStats" :key="name" 
               class="glass rounded-xl p-6">
            <h3 class="text-lg font-bold text-white mb-2">🤖 {{ name }}</h3>
            <p class="text-sm text-gray-400 mb-4">{{ stat.games }} 场对局</p>
            <div class="grid grid-cols-3 gap-4 text-center">
              <div>
                <div class="text-2xl font-bold text-game-accent-light">{{ formatPercent(stat.win_rate) }}</div>
                <div class="text-xs text-gray-500">总胜率</div>
              </div>
              <div>
                <div class="text-2xl font-bold text-wolf-red">{{ formatPercent(stat.wolf_win_rate) }}</div>
                <div class="text-xs text-gray-500">狼人胜率</div>
              </div>
              <div>
                <div class="text-2xl font-bold text-good-green">{{ formatPercent(stat.good_win_rate) }}</div>
                <div class="text-xs text-gray-500">好人胜率</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- History Tab -->
      <div v-if="activeTab === 'history'">
        <div class="glass rounded-2xl overflow-hidden">
          <div class="p-4 border-b border-game-border">
            <h2 class="text-lg font-semibold text-white">对局列表</h2>
          </div>
          
          <div v-if="loading" class="p-8 text-center text-gray-400">
            <div class="animate-spin w-8 h-8 border-4 border-game-accent border-t-transparent rounded-full mx-auto mb-4"></div>
            加载中...
          </div>
          
          <div v-else-if="games.length === 0" class="p-8 text-center text-gray-400">
            暂无对局记录
          </div>
          
          <div v-else>
            <div v-for="game in games" :key="game.game_id"
                 class="p-4 border-b border-game-border hover:bg-game-dark/50 transition-colors cursor-pointer"
                 @click="viewGame(game.game_id)">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-4">
                  <div :class="[
                    'w-12 h-12 rounded-xl flex items-center justify-center text-2xl',
                    game.winner_camp?.includes('狼人') ? 'bg-wolf-red/20' : 'bg-good-green/20'
                  ]">
                    {{ game.winner_camp?.includes('狼人') ? '🐺' : '👨‍🌾' }}
                  </div>
                  <div>
                    <div class="text-white font-medium">{{ formatGameId(game.game_id) }}</div>
                    <div class="text-sm text-gray-400">{{ formatDate(game.start_time) }}</div>
                  </div>
                </div>
                
                <div class="flex items-center space-x-6">
                  <div class="text-center">
                    <div class="text-white">{{ game.total_rounds }}</div>
                    <div class="text-xs text-gray-500">回合</div>
                  </div>
                  <div class="text-center">
                    <div class="text-white">{{ game.num_humans || 0 }}</div>
                    <div class="text-xs text-gray-500">真人</div>
                  </div>
                  <div class="text-center">
                    <div class="text-white">{{ formatDuration(game.duration) }}</div>
                    <div class="text-xs text-gray-500">时长</div>
                  </div>
                  <div :class="[
                    'px-3 py-1 rounded-full text-sm font-medium',
                    game.winner_camp?.includes('狼人') ? 'bg-wolf-red/20 text-wolf-red' : 'bg-good-green/20 text-good-green'
                  ]">
                    {{ game.winner_camp || '进行中' }}
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Pagination -->
          <div v-if="totalPages > 1" class="p-4 flex items-center justify-center space-x-2">
            <button @click="loadPage(currentPage - 1)" 
                    :disabled="currentPage === 1"
                    class="px-4 py-2 rounded-lg bg-game-dark text-gray-400 
                           hover:text-white disabled:opacity-50 disabled:cursor-not-allowed">
              上一页
            </button>
            <span class="text-gray-400">
              {{ currentPage }} / {{ totalPages }}
            </span>
            <button @click="loadPage(currentPage + 1)" 
                    :disabled="currentPage === totalPages"
                    class="px-4 py-2 rounded-lg bg-game-dark text-gray-400 
                           hover:text-white disabled:opacity-50 disabled:cursor-not-allowed">
              下一页
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { statsApi } from '@/api'

const router = useRouter()

const tabs = [
  { key: 'overview', name: '总览', icon: '📊' },
  { key: 'roles', name: '角色统计', icon: '🎭' },
  { key: 'personalities', name: '人格统计', icon: '🧠' },
  { key: 'models', name: '模型统计', icon: '🤖' },
  { key: 'history', name: '对局历史', icon: '📜' },
]

const activeTab = ref('overview')
const loading = ref(true)

// Stats data
const stats = ref({
  total_games: 0,
  total_rounds: 0,
  wolf_wins: 0,
  good_wins: 0,
  wolf_win_rate: 0,
  good_win_rate: 0,
  avg_duration: 0,
})
const roleStats = ref({})
const personalityStats = ref({})
const modelStats = ref({})

// History data
const games = ref([])
const currentPage = ref(1)
const totalPages = ref(1)

const getRoleIcon = (role) => {
  const icons = {
    '狼人': '🐺',
    '村民': '👨‍🌾',
    '预言家': '🔮',
    '女巫': '🧙‍♀️',
    '猎人': '🏹',
    '守卫': '🛡️',
  }
  return icons[role] || '❓'
}

const formatPercent = (value) => {
  if (value === undefined || value === null) return '0.0%'
  return (value * 100).toFixed(1) + '%'
}

const formatAvgDuration = (seconds) => {
  if (!seconds) return '0分'
  const m = Math.floor(seconds / 60)
  return `${m}分`
}

const formatGameId = (id) => {
  if (!id) return '-'
  const parts = id.split('_')
  if (parts.length >= 3) {
    return `对局 ${parts[1]} ${parts[2]}`
  }
  return id
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const formatDuration = (seconds) => {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}分${s}秒`
}

const loadPage = async (page) => {
  if (page < 1 || page > totalPages.value) return
  
  loading.value = true
  try {
    const res = await statsApi.getHistory(page, 20)
    games.value = res.data.games || []
    currentPage.value = res.data.page
    totalPages.value = res.data.pages
  } catch (error) {
    console.error('加载历史记录失败：', error)
  } finally {
    loading.value = false
  }
}

const viewGame = (gameId) => {
  router.push(`/history/${gameId}`)
}

onMounted(async () => {
  try {
    // 并行加载所有数据
    const [overviewRes, rolesRes, personalitiesRes, modelsRes, historyRes] = await Promise.all([
      statsApi.getOverview(),
      statsApi.getRoleStats(),
      statsApi.getPersonalityStats(),
      statsApi.getModelStats(),
      statsApi.getHistory(1, 20)
    ])
    
    stats.value = overviewRes.data || {}
    roleStats.value = rolesRes.data || {}
    personalityStats.value = personalitiesRes.data || {}
    modelStats.value = modelsRes.data || {}
    games.value = historyRes.data?.games || []
    totalPages.value = historyRes.data?.pages || 1
  } catch (error) {
    console.error('加载统计数据失败：', error)
  } finally {
    loading.value = false
  }
})
</script>
