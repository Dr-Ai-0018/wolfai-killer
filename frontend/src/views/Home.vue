<template>
  <div class="min-h-screen">
    <!-- Hero Section -->
    <section class="relative py-20 px-4 overflow-hidden">
      <div class="max-w-6xl mx-auto text-center">
        <div class="mb-8 animate-float">
          <img src="/wolf.svg" alt="狼人图标" class="w-32 h-32 mx-auto" />
        </div>
        <h1 class="text-5xl md:text-7xl font-bold mb-6">
          <span class="text-white">智能 </span>
          <span class="text-game-accent-light">狼人杀</span>
        </h1>
        <p class="text-xl text-gray-400 mb-8 max-w-2xl mx-auto">
          与 12 种独特人格的智能玩家一起，体验前所未有的狼人杀对局。
          每个智能玩家都有自己的思维方式和行为风格。
        </p>
        <div class="flex flex-wrap justify-center gap-4">
          <router-link 
            to="/setup"
            class="inline-flex items-center px-8 py-4 bg-game-accent hover:bg-game-accent-light 
                   text-white font-semibold rounded-xl transition-all transform hover:scale-105
                   shadow-lg shadow-game-accent/30"
          >
            <span class="mr-2">🎮</span>
            开始游戏
          </router-link>
          <router-link 
            to="/history"
            class="inline-flex items-center px-6 py-4 bg-gray-700 hover:bg-gray-600 
                   text-white font-semibold rounded-xl transition-all transform hover:scale-105"
          >
            <span class="mr-2">📊</span>
            历史记录
          </router-link>
          <router-link 
            to="/admin"
            class="inline-flex items-center px-6 py-4 bg-purple-700 hover:bg-purple-600 
                   text-white font-semibold rounded-xl transition-all transform hover:scale-105"
          >
            <span class="mr-2">⚙️</span>
            管理面板
          </router-link>
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="py-16 px-4">
      <div class="max-w-6xl mx-auto">
        <h2 class="text-3xl font-bold text-center mb-12 text-white">游戏特色</h2>
        <div class="grid md:grid-cols-3 gap-8">
          <div class="glass rounded-2xl p-6 card-hover">
            <div class="text-4xl mb-4">🤖</div>
            <h3 class="text-xl font-semibold text-white mb-2">多模型智能玩家</h3>
            <p class="text-gray-400">
              支持多种先进的大语言模型，每个智能玩家都能进行深度推理和策略分析。
            </p>
          </div>
          <div class="glass rounded-2xl p-6 card-hover">
            <div class="text-4xl mb-4">🎭</div>
            <h3 class="text-xl font-semibold text-white mb-2">12 种人格</h3>
            <p class="text-gray-400">
              从勇敢领袖到佛系摆烂，每种人格都有独特的发言风格和决策倾向。
            </p>
          </div>
          <div class="glass rounded-2xl p-6 card-hover">
            <div class="text-4xl mb-4">👥</div>
            <h3 class="text-xl font-semibold text-white mb-2">人机混战</h3>
            <p class="text-gray-400">
              支持真人玩家与智能玩家混合对战，体验真实的狼人杀博弈乐趣。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Roles Section -->
    <section class="py-16 px-4 bg-game-dark/50">
      <div class="max-w-6xl mx-auto">
        <h2 class="text-3xl font-bold text-center mb-12 text-white">角色介绍</h2>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div v-for="role in roles" :key="role.code" 
               class="glass rounded-xl p-4 text-center card-hover cursor-pointer"
               @click="selectedRole = role">
            <div class="text-4xl mb-2">{{ role.icon }}</div>
            <h4 class="font-semibold text-white">{{ role.name }}</h4>
            <p class="text-xs text-gray-400 mt-1">{{ role.camp }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Personalities Section -->
    <section class="py-16 px-4">
      <div class="max-w-6xl mx-auto">
        <h2 class="text-3xl font-bold text-center mb-12 text-white">智能玩家人格</h2>
        <div class="grid md:grid-cols-4 gap-4">
          <div v-for="p in personalities" :key="p.code" 
               class="glass rounded-xl p-4 card-hover">
            <h4 class="font-semibold text-game-accent-light mb-2">{{ p.name }}</h4>
            <p class="text-sm text-gray-400">{{ p.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Stats Section -->
    <section class="py-16 px-4 bg-game-dark/50">
      <div class="max-w-6xl mx-auto">
        <h2 class="text-3xl font-bold text-center mb-12 text-white">游戏统计</h2>
        <div class="grid md:grid-cols-4 gap-6">
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-game-accent-light mb-2">
              {{ stats.total_games || 0 }}
            </div>
            <div class="text-gray-400">总对局数</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-game-accent-light mb-2">
              {{ stats.total_rounds || 0 }}
            </div>
            <div class="text-gray-400">总回合数</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-wolf-red mb-2">
              {{ ((stats.wolf_win_rate || 0) * 100).toFixed(1) }}%
            </div>
            <div class="text-gray-400">狼人胜率</div>
          </div>
          <div class="glass rounded-xl p-6 text-center">
            <div class="text-4xl font-bold text-good-green mb-2">
              {{ ((stats.good_win_rate || 0) * 100).toFixed(1) }}%
            </div>
            <div class="text-gray-400">好人胜率</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Role Detail Modal -->
    <div v-if="selectedRole" 
         class="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
         @click.self="selectedRole = null">
      <div class="glass rounded-2xl p-8 max-w-lg w-full">
        <div class="flex items-center mb-4">
          <span class="text-5xl mr-4">{{ selectedRole.icon }}</span>
          <div>
            <h3 class="text-2xl font-bold text-white">{{ selectedRole.name }}</h3>
            <p class="text-game-accent-light">{{ selectedRole.camp }}</p>
          </div>
        </div>
        <p class="text-gray-300 mb-4">{{ selectedRole.description }}</p>
        <div class="mb-4">
          <h4 class="font-semibold text-white mb-2">技能</h4>
          <ul class="list-disc list-inside text-gray-400">
            <li v-for="ability in selectedRole.abilities" :key="ability">{{ ability }}</li>
          </ul>
        </div>
        <div>
          <h4 class="font-semibold text-white mb-2">胜利条件</h4>
          <p class="text-gray-400">{{ selectedRole.win_condition }}</p>
        </div>
        <button @click="selectedRole = null" 
                class="mt-6 w-full py-3 bg-game-accent hover:bg-game-accent-light 
                       rounded-xl text-white font-semibold transition-colors">
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { configApi, statsApi } from '@/api'
import { DEFAULT_HOME_PERSONALITIES, DEFAULT_HOME_ROLES, fetchHomePageData } from '@/homeContent'

const roles = ref([])
const personalities = ref([])
const stats = ref({})
const selectedRole = ref(null)

onMounted(async () => {
  // 先设置默认值
  roles.value = DEFAULT_HOME_ROLES
  personalities.value = DEFAULT_HOME_PERSONALITIES
  
  try {
    const payload = await fetchHomePageData(configApi, statsApi)
    if (payload.roles) roles.value = payload.roles
    if (payload.personalities) personalities.value = payload.personalities
    if (payload.stats) stats.value = payload.stats
  } catch (error) {
    console.error('加载首页数据失败：', error)
    // 保持默认数据
  }
})
</script>
