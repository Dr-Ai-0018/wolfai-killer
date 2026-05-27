export const PLAYER_OPTIONS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

export const WOLF_ROLE_CODES = ['WOLF', 'WOLF_KING', 'WHITE_WOLF', 'BEAUTY']

export const DEFAULT_ROLES = [
  { code: 'WOLF', name: '狼人', camp: '狼人阵营', icon: '🐺' },
  { code: 'WOLF_KING', name: '狼王', camp: '狼人阵营', icon: '👑' },
  { code: 'WHITE_WOLF', name: '白狼王', camp: '狼人阵营', icon: '🐺' },
  { code: 'BEAUTY', name: '狼美人', camp: '狼人阵营', icon: '💋' },
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
  { code: 'VILLAGER', name: '村民', camp: '好人阵营', icon: '👨‍🌾' },
]

export const DEFAULT_MODELS = [
  { id: 'bl-DeepSeek-V3-250324', label: 'bl-DeepSeek-V3-250324' },
  { id: 'bl-DeepSeek-V3.1', label: 'bl-DeepSeek-V3.1' },
  { id: 'bl-DeepSeek-V3.2-Exp', label: 'bl-DeepSeek-V3.2-Exp' },
]

export function buildEmptyRoleConfig() {
  return {
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
    VILLAGER: 0,
  }
}

export function getMaxWolves(totalPlayers) {
  return Math.max(1, Math.floor((totalPlayers - 1) / 3))
}

export function buildWolfOptions(totalPlayers) {
  const maxWolves = getMaxWolves(totalPlayers)
  return Array.from({ length: maxWolves }, (_, i) => i + 1)
}

export function buildRecommendedRoleConfig(totalPlayers) {
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
  return roleConfig
}

export function withBalancedVillagers(roleConfig, totalPlayers) {
  let nonVillagerCount = 0
  for (const [code, count] of Object.entries(roleConfig)) {
    if (code !== 'VILLAGER') {
      nonVillagerCount += count
    }
  }
  return {
    ...roleConfig,
    VILLAGER: Math.max(0, totalPlayers - nonVillagerCount),
  }
}

export function countWolves(roleConfig) {
  return WOLF_ROLE_CODES.reduce((sum, code) => sum + (roleConfig[code] || 0), 0)
}

export function canIncreaseRoleCount(code, roleConfig, totalPlayers) {
  const totalRoleCount = Object.values(roleConfig).reduce((sum, count) => sum + count, 0)
  if (WOLF_ROLE_CODES.includes(code)) {
    return countWolves(roleConfig) < getMaxWolves(totalPlayers)
  }
  if (code === 'VILLAGER') {
    return totalRoleCount < totalPlayers
  }
  return (roleConfig[code] || 0) < 1
}

export function canDecreaseRoleCount(code, roleConfig, totalPlayers) {
  if (WOLF_ROLE_CODES.includes(code)) {
    if (code === 'WOLF') {
      if (totalPlayers === 5) {
        return roleConfig.WOLF > 1
      }
      const otherWolves = countWolves(roleConfig) - roleConfig.WOLF
      return roleConfig.WOLF > (otherWolves > 0 ? 0 : 1)
    }
    return (roleConfig[code] || 0) > 0
  }
  if (code === 'VILLAGER') {
    return roleConfig.VILLAGER > 0
  }
  return (roleConfig[code] || 0) > 0
}

export function getModelId(model) {
  if (typeof model === 'string') return model
  return model?.id || model?.name || model?.model || ''
}

export function getModelLabel(model) {
  if (typeof model === 'string') return model
  return model?.label || getModelId(model)
}

export function buildSeatModelMap(seatModelMap) {
  const filtered = {}
  for (const [seat, model] of Object.entries(seatModelMap)) {
    if (model) {
      filtered[Number.parseInt(seat, 10)] = model
    }
  }
  return filtered
}
