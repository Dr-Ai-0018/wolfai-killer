<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-4xl mx-auto">
      <h1 class="text-3xl font-bold text-white mb-8 text-center">游戏设置</h1>
      
      <!-- Player Configuration -->
      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-xl font-semibold text-white mb-4">👥 玩家配置</h2>
        
        <div class="grid md:grid-cols-2 gap-6">
          <div>
            <label class="block text-gray-400 mb-2">总人数</label>
            <select v-model="config.totalPlayers" @change="onTotalPlayersChange"
                    class="w-full bg-game-dark border border-game-border rounded-lg px-4 py-3 text-white">
              <option v-for="n in playerOptions" :key="n" :value="n">{{ n }} 人局</option>
            </select>
          </div>
          
          <div>
            <label class="block text-gray-400 mb-2">狼人数量</label>
            <select v-model="config.roleConfig.WOLF" @change="updateVillagerCount"
                    class="w-full bg-game-dark border border-game-border rounded-lg px-4 py-3 text-white">
              <option v-for="n in wolfOptions" :key="n" :value="n">{{ n }} 狼</option>
            </select>
          </div>
        </div>

        <div v-if="smallLobbyWarning" class="mt-4 rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
          <div class="text-sm font-medium text-amber-300 mb-1">小局风险提示</div>
          <p class="text-sm text-amber-100/80 leading-relaxed">
            5 到 6 人局波动很大。当前版本里，`5人2狼` 明显偏狼强，`5人1狼` 又容易偏好人强。
            当前默认 `5人局` 只是偏保守、偏好人侧的临时推荐；即使收紧了女巫首夜救人，它仍未验证平衡。不要手动堆出极端狼人数。
          </p>
        </div>
        
        <!-- Human Seat Selection -->
        <div class="mt-6">
          <label class="block text-gray-400 mb-2">选择你的座位号（真人玩家）</label>
          <div class="flex flex-wrap gap-2">
            <button v-for="seat in config.totalPlayers" :key="seat"
                    @click="toggleHumanSeat(seat)"
                    :class="[
                      'w-12 h-12 rounded-lg font-semibold transition-all',
                      config.humanSeats.includes(seat) 
                        ? 'bg-game-accent text-white' 
                        : 'bg-game-dark border border-game-border text-gray-400 hover:border-game-accent'
                    ]">
              {{ seat }}
            </button>
          </div>
          <p class="text-sm text-gray-500 mt-2">
            已选择 {{ config.humanSeats.length }} 个真人玩家座位
            <span v-if="config.humanSeats.length === 0" class="text-yellow-500">
              （不选择则全部为智能玩家对战）
            </span>
          </p>
        </div>
      </div>

      <!-- Role Configuration -->
      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-xl font-semibold text-white mb-4">🎭 角色配置</h2>
        
        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div v-for="role in roles" :key="role.code"
               class="bg-game-dark rounded-xl p-4 border border-game-border">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center">
                <span class="text-2xl mr-2">{{ role.icon }}</span>
                <span class="text-white font-medium">{{ role.name }}</span>
              </div>
              <span :class="[
                'text-xs px-2 py-1 rounded',
                role.camp === '狼人阵营' ? 'bg-wolf-red/20 text-wolf-red' : 'bg-good-green/20 text-good-green'
              ]">
                {{ role.camp === '狼人阵营' ? '狼' : '好人' }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-gray-400 text-sm">数量</span>
              <div class="flex items-center space-x-2">
                <button @click="decreaseRole(role.code)" 
                        :disabled="!canDecreaseRole(role.code)"
                        class="w-8 h-8 rounded bg-game-border text-white hover:bg-game-accent disabled:opacity-30 disabled:cursor-not-allowed">
                  -
                </button>
                <span class="text-game-accent-light font-semibold w-6 text-center">
                  {{ config.roleConfig[role.code] || 0 }}
                </span>
                <button @click="increaseRole(role.code)" 
                        :disabled="!canIncreaseRole(role.code)"
                        class="w-8 h-8 rounded bg-game-border text-white hover:bg-game-accent disabled:opacity-30 disabled:cursor-not-allowed">
                  +
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <div class="mt-4 p-3 rounded-lg" :class="roleCountValid && wolfCountValid ? 'bg-good-green/10' : 'bg-wolf-red/10'">
          <p :class="roleCountValid && wolfCountValid ? 'text-good-green' : 'text-wolf-red'">
            当前配置：{{ totalRoleCount }} / {{ config.totalPlayers }} 人
            <span v-if="!roleCountValid">(请调整角色数量)</span>
            <span v-else-if="!wolfCountValid">(狼人阵营人数过多，当前人数局不允许)</span>
          </p>
        </div>

        <div class="mt-4 rounded-xl border border-sky-500/20 bg-sky-950/20 p-4">
          <div class="text-sm font-medium text-sky-200 mb-1">扩展角色提示</div>
          <p class="text-sm text-sky-100/75 leading-relaxed">
            当前已优先接入并建议测试的扩展角色：`丘比特`、`长老`、`白痴`、`野孩子`、`共济会`、`圣徒`。
            现已补充 `被诅咒者`、`受祝福者`、`狐狸`、`天使`、`替罪羊` 作为低耦合扩展角色。
            `狼王`、`白狼王`、`狼美人` 仍以占位为主，暂不建议正式开局使用。
          </p>
        </div>
      </div>

      <!-- 智能玩家配置 -->
      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-xl font-semibold text-white mb-4">🤖 智能玩家配置</h2>
        
        <div class="space-y-4">
          <label class="flex items-center cursor-pointer">
            <input type="checkbox" v-model="config.aiConfig.randomModel" 
                   class="w-5 h-5 rounded bg-game-dark border-game-border text-game-accent focus:ring-game-accent">
            <span class="ml-3 text-white">随机分配智能玩家模型</span>
          </label>
          
          <label class="flex items-center cursor-pointer">
            <input type="checkbox" v-model="config.aiConfig.randomPersonality" 
                   class="w-5 h-5 rounded bg-game-dark border-game-border text-game-accent focus:ring-game-accent">
            <span class="ml-3 text-white">随机分配智能玩家人格</span>
          </label>
        </div>
        
        <!-- Manual Model Assignment -->
        <div v-if="!config.aiConfig.randomModel" class="mt-6 p-4 bg-game-dark/50 rounded-xl border border-game-border">
          <h4 class="text-sm font-medium text-white mb-4 flex items-center">
            <span class="mr-2">⚙️</span>
            为每个智能玩家座位分配模型
          </h4>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            <div v-for="seat in config.totalPlayers" :key="seat"
                 class="flex items-center gap-2">
              <span class="text-sm text-gray-400 w-16">
                {{ seat }}号位
                <span v-if="config.humanSeats.includes(seat)" class="text-game-accent">(人)</span>
              </span>
              <select v-if="!config.humanSeats.includes(seat)"
                      v-model="config.seatModelMap[seat]"
                      class="flex-1 bg-game-dark border border-game-border rounded-lg px-3 py-2 text-sm text-white
                             focus:border-game-accent focus:outline-none">
                <option value="">默认模型</option>
                <option v-for="model in models" :key="getModelId(model)" :value="getModelId(model)">
                  {{ getModelLabel(model) }}
                </option>
              </select>
              <span v-else class="flex-1 text-xs text-gray-500 italic">真人玩家</span>
            </div>
          </div>
          <p class="text-xs text-gray-500 mt-3">
            提示：未指定的智能玩家座位将使用第一个可用模型
          </p>
        </div>
        
        <div class="mt-4 p-4 bg-game-dark/50 rounded-lg">
          <h4 class="text-sm font-medium text-gray-400 mb-2">可用模型 ({{ models.length }})</h4>
          <div class="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
            <span v-for="model in models" :key="getModelId(model)"
                  class="px-3 py-1 bg-game-border/50 rounded-full text-sm text-gray-300">
              {{ getModelLabel(model) }}
            </span>
          </div>
        </div>
      </div>

      <!-- God Mode Configuration -->
      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-xl font-semibold text-white mb-4">👁️ 上帝模式</h2>
        
        <div class="space-y-4">
          <label class="flex items-center cursor-pointer">
            <input type="checkbox" v-model="config.godMode.enabled" 
                   class="w-5 h-5 rounded bg-game-dark border-game-border text-game-accent focus:ring-game-accent">
            <span class="ml-3 text-white">启用上帝模式</span>
          </label>
          
          <p class="text-sm text-gray-500">
            启用后，可以在游戏中随时查看所有隐藏信息（包括夜晚行动、玩家身份等）
          </p>
          
          <div v-if="config.godMode.enabled" class="mt-4 space-y-3">
            <div>
              <label class="block text-gray-400 mb-2">设置上帝模式密码</label>
              <input type="password" v-model="config.godMode.password" 
                     placeholder="输入密码..."
                     class="w-full bg-game-dark border border-game-border rounded-lg px-4 py-3 text-white 
                            focus:border-game-accent focus:outline-none">
            </div>
            <div>
              <label class="block text-gray-400 mb-2">确认密码</label>
              <input type="password" v-model="config.godMode.confirmPassword" 
                     placeholder="再次输入密码..."
                     class="w-full bg-game-dark border border-game-border rounded-lg px-4 py-3 text-white 
                            focus:border-game-accent focus:outline-none">
            </div>
            <p v-if="passwordError" class="text-red-500 text-sm">{{ passwordError }}</p>
          </div>
        </div>
      </div>

      <!-- Start Button -->
      <div class="text-center">
        <button @click="createGame" 
                :disabled="loading"
                class="px-12 py-4 bg-game-accent hover:bg-game-accent-light 
                       text-white font-semibold rounded-xl transition-all 
                       transform hover:scale-105 shadow-lg shadow-game-accent/30
                       disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none">
          <span v-if="loading" class="flex items-center">
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            创建中...
          </span>
          <span v-else>🎮 创建游戏</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { configApi, gameApi } from '@/api'

const router = useRouter()

const roles = ref([])
const models = ref([])
const loading = ref(false)

const config = ref({
  totalPlayers: 12,
  humanSeats: [],
  roleConfig: {
    // 狼人阵营
    WOLF: 3,
    WOLF_KING: 0,
    WHITE_WOLF: 0,
    BEAUTY: 0,
    // 好人阵营 - 神职
    SEER: 1,
    WITCH: 1,
    GUARD: 1,
    HUNTER: 1,
    FOX: 0,
    ANGEL: 0,
    SCAPEGOAT: 0,
    MASON: 0,
    SUPER_SAINT: 0,
    CUPID: 0,
    IDIOT: 0,
    ELDER: 0,
    WILD_CHILD: 0,
    CURSED: 0,
    BLESSED: 0,
    // 好人阵营 - 平民
    VILLAGER: 5
  },
  aiConfig: {
    randomModel: true,
    randomPersonality: true
  },
  seatModelMap: {},  // Manual model assignment: seat -> model_name
  godMode: {
    enabled: false,
    password: '',
    confirmPassword: ''
  }
})

// 可选人数范围
const playerOptions = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

// 狼人数量选项（根据总人数动态计算）
const wolfOptions = computed(() => {
  const total = config.value.totalPlayers
  const maxWolves = Math.max(1, Math.floor((total - 1) / 3))
  return Array.from({ length: maxWolves }, (_, i) => i + 1)
})

// 总角色数
const totalRoleCount = computed(() => {
  return Object.values(config.value.roleConfig).reduce((sum, count) => sum + count, 0)
})

// 角色数量是否有效
const roleCountValid = computed(() => {
  return totalRoleCount.value === config.value.totalPlayers
})

const wolfCountValid = computed(() => {
  const maxWolves = Math.max(1, Math.floor((config.value.totalPlayers - 1) / 3))
  return totalWolfCount.value >= 1 && totalWolfCount.value <= maxWolves
})

const smallLobbyWarning = computed(() => config.value.totalPlayers <= 6)

const passwordError = computed(() => {
  if (!config.value.godMode.enabled) return ''
  if (!config.value.godMode.password) return '请设置密码'
  if (config.value.godMode.password.length < 4) return '密码至少 4 位'
  if (config.value.godMode.password !== config.value.godMode.confirmPassword) return '两次密码不一致'
  return ''
})

// 总人数变化时调整角色配置
const onTotalPlayersChange = () => {
  // 清理超出范围的真人座位
  config.value.humanSeats = config.value.humanSeats.filter(s => s <= config.value.totalPlayers)
  applyRecommendedSetup(config.value.totalPlayers)
}

// 更新村民数量（自动填充）
const updateVillagerCount = () => {
  let nonVillagerCount = 0
  for (const [code, count] of Object.entries(config.value.roleConfig)) {
    if (code !== 'VILLAGER') {
      nonVillagerCount += count
    }
  }
  config.value.roleConfig.VILLAGER = Math.max(0, config.value.totalPlayers - nonVillagerCount)
}

// 增加角色数量
const increaseRole = (code) => {
  if (canIncreaseRole(code)) {
    config.value.roleConfig[code]++
    if (code !== 'VILLAGER') {
      updateVillagerCount()
    }
  }
}

// 减少角色数量
const decreaseRole = (code) => {
  if (canDecreaseRole(code)) {
    config.value.roleConfig[code]--
    if (code !== 'VILLAGER') {
      updateVillagerCount()
    }
  }
}

// 狼人阵营角色
const wolfRoles = ['WOLF', 'WOLF_KING', 'WHITE_WOLF', 'BEAUTY']

// 计算当前狼人总数
const totalWolfCount = computed(() => {
  return wolfRoles.reduce((sum, code) => sum + (config.value.roleConfig[code] || 0), 0)
})

// 是否可以增加
const canIncreaseRole = (code) => {
  // 狼人阵营角色
  if (wolfRoles.includes(code)) {
    const maxWolves = Math.max(1, Math.floor((config.value.totalPlayers - 1) / 3))
    return totalWolfCount.value < maxWolves
  }
  if (code === 'VILLAGER') {
    return totalRoleCount.value < config.value.totalPlayers
  }
  // 神职最多 1 个
  return (config.value.roleConfig[code] || 0) < 1
}

// 是否可以减少
const canDecreaseRole = (code) => {
  // 狼人阵营角色
  if (wolfRoles.includes(code)) {
    if (code === 'WOLF') {
      if (config.value.totalPlayers === 5) {
        return config.value.roleConfig.WOLF > 1
      }
      // 普通狼人至少要有 1 个（如果没有其他狼人角色）
      const otherWolves = totalWolfCount.value - config.value.roleConfig.WOLF
      return config.value.roleConfig.WOLF > (otherWolves > 0 ? 0 : 1)
    }
    return (config.value.roleConfig[code] || 0) > 0
  }
  if (code === 'VILLAGER') {
    return config.value.roleConfig.VILLAGER > 0
  }
  return (config.value.roleConfig[code] || 0) > 0
}

const toggleHumanSeat = (seat) => {
  const index = config.value.humanSeats.indexOf(seat)
  if (index > -1) {
    config.value.humanSeats.splice(index, 1)
  } else {
    config.value.humanSeats.push(seat)
  }
}

const buildEmptyRoleConfig = () => ({
  WOLF: 0,
  WOLF_KING: 0,
  WHITE_WOLF: 0,
  BEAUTY: 0,
  SEER: 0,
  WITCH: 0,
  GUARD: 0,
  HUNTER: 0,
  FOX: 0,
  ANGEL: 0,
  SCAPEGOAT: 0,
  MASON: 0,
  SUPER_SAINT: 0,
  CUPID: 0,
  IDIOT: 0,
  ELDER: 0,
  WILD_CHILD: 0,
  CURSED: 0,
  BLESSED: 0,
  VILLAGER: 0
})

const applyRecommendedSetup = (totalPlayers) => {
  const roleConfig = buildEmptyRoleConfig()

  if (totalPlayers === 5) {
    Object.assign(roleConfig, { WOLF: 1, SEER: 1, WITCH: 1, VILLAGER: 2 })
  } else if (totalPlayers === 6) {
    Object.assign(roleConfig, { WOLF: 2, SEER: 1, WITCH: 1, GUARD: 1, VILLAGER: 1 })
  } else if (totalPlayers === 7) {
    Object.assign(roleConfig, { WOLF: 2, SEER: 1, WITCH: 1, GUARD: 1, HUNTER: 1, VILLAGER: 1 })
  } else if (totalPlayers === 8) {
    Object.assign(roleConfig, { WOLF: 2, SEER: 1, WITCH: 1, GUARD: 1, HUNTER: 1, VILLAGER: 2 })
  } else {
    roleConfig.WOLF = Math.min(Math.floor(totalPlayers / 3), 3)
    roleConfig.SEER = 1
    roleConfig.WITCH = 1
    roleConfig.GUARD = 1
    roleConfig.HUNTER = 1
    roleConfig.VILLAGER = Math.max(0, totalPlayers - roleConfig.WOLF - 4)
    const assigned = Object.values(roleConfig).reduce((sum, count) => sum + count, 0)
    roleConfig.VILLAGER += Math.max(0, totalPlayers - assigned)
  }

  config.value.roleConfig = roleConfig
  updateVillagerCount()
}

const getModelId = (model) => {
  if (typeof model === 'string') return model
  return model?.id || model?.name || model?.model || ''
}

const getModelLabel = (model) => {
  if (typeof model === 'string') return model
  return model?.label || getModelId(model)
}

const createGame = async () => {
  // 验证角色数量
  if (!roleCountValid.value) {
    alert('角色数量不匹配，请调整配置')
    return
  }
  if (!wolfCountValid.value) {
    alert('狼人阵营人数过多，当前人数局不允许')
    return
  }
  
  // 验证上帝模式密码
  if (config.value.godMode.enabled && passwordError.value) {
    alert(passwordError.value)
    return
  }
  
  loading.value = true
  try {
    // Build seat model map (filter out empty values)
    const seatModelMap = {}
    if (!config.value.aiConfig.randomModel) {
      for (const [seat, model] of Object.entries(config.value.seatModelMap)) {
        if (model) {
          seatModelMap[parseInt(seat)] = model
        }
      }
    }
    
    const response = await gameApi.create({
      total_players: config.value.totalPlayers,
      num_wolves: config.value.roleConfig.WOLF,
      role_config: config.value.roleConfig,
      human_seats: config.value.humanSeats,
      random_models: config.value.aiConfig.randomModel,
      seat_model_map: Object.keys(seatModelMap).length > 0 ? seatModelMap : null,
      god_mode: config.value.godMode.enabled ? {
        enabled: true,
        password: config.value.godMode.password
      } : null
    })
    
    const gameId = response.data.game_id
    router.push(`/game/${gameId}`)
  } catch (error) {
    console.error('创建游戏失败：', error)
    alert('创建游戏失败，请重试')
  } finally {
    loading.value = false
  }
}

// 默认数据 - 包含所有角色
const defaultRoles = [
  // 狼人阵营
  { code: 'WOLF', name: '狼人', camp: '狼人阵营', icon: '🐺' },
  { code: 'WOLF_KING', name: '狼王', camp: '狼人阵营', icon: '👑' },
  { code: 'WHITE_WOLF', name: '白狼王', camp: '狼人阵营', icon: '🐺' },
  { code: 'BEAUTY', name: '狼美人', camp: '狼人阵营', icon: '💋' },
  // 好人阵营 - 神职
  { code: 'SEER', name: '预言家', camp: '好人阵营', icon: '🔮' },
  { code: 'WITCH', name: '女巫', camp: '好人阵营', icon: '🧙‍♀️' },
  { code: 'GUARD', name: '守卫', camp: '好人阵营', icon: '🛡️' },
  { code: 'HUNTER', name: '猎人', camp: '好人阵营', icon: '🏹' },
  { code: 'FOX', name: '狐狸', camp: '好人阵营', icon: '🦊' },
  { code: 'ANGEL', name: '天使', camp: '第三方阵营', icon: '😇' },
  { code: 'SCAPEGOAT', name: '替罪羊', camp: '好人阵营', icon: '🐐' },
  { code: 'MASON', name: '共济会', camp: '好人阵营', icon: '🤝' },
  { code: 'SUPER_SAINT', name: '圣徒', camp: '好人阵营', icon: '⛪' },
  { code: 'CUPID', name: '丘比特', camp: '好人阵营', icon: '💘' },
  { code: 'IDIOT', name: '白痴', camp: '好人阵营', icon: '🤪' },
  { code: 'ELDER', name: '长老', camp: '好人阵营', icon: '👴' },
  { code: 'WILD_CHILD', name: '野孩子', camp: '好人阵营', icon: '🧒' },
  { code: 'CURSED', name: '被诅咒者', camp: '好人阵营', icon: '🕯️' },
  { code: 'BLESSED', name: '受祝福者', camp: '好人阵营', icon: '✨' },
  // 好人阵营 - 平民
  { code: 'VILLAGER', name: '村民', camp: '好人阵营', icon: '👨‍🌾' }
]

const defaultModels = [
  { id: 'bl-DeepSeek-V3-250324', label: 'bl-DeepSeek-V3-250324' },
  { id: 'bl-DeepSeek-V3.1', label: 'bl-DeepSeek-V3.1' },
  { id: 'bl-DeepSeek-V3.2-Exp', label: 'bl-DeepSeek-V3.2-Exp' }
]

onMounted(async () => {
  applyRecommendedSetup(config.value.totalPlayers)
  // 先设置默认值
  roles.value = defaultRoles
  models.value = defaultModels
  
  try {
    const [rolesRes, modelsRes] = await Promise.all([
      configApi.getRoles(),
      configApi.getModels()
    ])
    // 只有当返回数据有效时才更新
    if (rolesRes.data && Array.isArray(rolesRes.data) && rolesRes.data.length > 0) {
      roles.value = rolesRes.data
    }
    if (modelsRes.data && Array.isArray(modelsRes.data) && modelsRes.data.length > 0) {
      models.value = modelsRes.data
    }
  } catch (error) {
    console.error('加载配置失败：', error)
    // 保持默认数据
  }
})
</script>
