export const DEFAULT_HOME_ROLES = [
  {
    code: 'WOLF',
    name: '狼人',
    camp: '狼人阵营',
    icon: '🐺',
    description: '狼人是狼人阵营的核心角色。每晚狼人们会一起讨论并选择一名玩家进行袭击。',
    abilities: ['夜晚与其他狼人一起选择袭击目标'],
    win_condition: '当狼人数量大于等于好人数量时获胜',
  },
  {
    code: 'VILLAGER',
    name: '村民',
    camp: '好人阵营',
    icon: '👨‍🌾',
    description: '村民是好人阵营的普通角色，没有特殊技能。',
    abilities: ['白天投票处决可疑玩家'],
    win_condition: '当所有狼人被消灭时获胜',
  },
  {
    code: 'SEER',
    name: '预言家',
    camp: '好人阵营',
    icon: '🔮',
    description: '预言家是好人阵营最重要的神职角色。每晚可以查验一名玩家的阵营身份。',
    abilities: ['每晚查验一名玩家的阵营'],
    win_condition: '当所有狼人被消灭时获胜',
  },
  {
    code: 'WITCH',
    name: '女巫',
    camp: '好人阵营',
    icon: '🧙‍♀️',
    description: '女巫拥有两瓶药水：解药可以救活被狼人袭击的玩家，毒药可以毒死任意一名玩家。',
    abilities: ['解药：救活被狼人袭击的玩家', '毒药：毒死任意一名玩家'],
    win_condition: '当所有狼人被消灭时获胜',
  },
  {
    code: 'HUNTER',
    name: '猎人',
    camp: '好人阵营',
    icon: '🏹',
    description: '猎人在被投票处决或被狼人袭击死亡时，可以选择开枪带走一名玩家。',
    abilities: ['死亡时可以开枪带走一名玩家'],
    win_condition: '当所有狼人被消灭时获胜',
  },
  {
    code: 'GUARD',
    name: '守卫',
    camp: '好人阵营',
    icon: '🛡️',
    description: '守卫每晚可以选择守护一名玩家，被守护的玩家当晚不会被狼人袭击致死。',
    abilities: ['每晚守护一名玩家免受狼人袭击'],
    win_condition: '当所有狼人被消灭时获胜',
  },
]

export const DEFAULT_HOME_PERSONALITIES = [
  { code: 'leader_bold', name: '勇敢领袖型', description: '敢于发言、敢带节奏、愿意拍板做决定' },
  { code: 'careful_timid', name: '胆小细腻型', description: '谨慎、怕背锅，喜欢观望和跟票' },
  { code: 'aggressive', name: '激进冲锋型', description: '喜欢强势发言和发起冲票' },
  { code: 'schemer', name: '老谋深算型', description: '重视长期收益，会刻意隐藏真实想法' },
  { code: 'buddha', name: '佛系摆烂型', description: '偏随缘，不太愿意深度推理' },
  { code: 'rational_analyst', name: '理性分析型', description: '偏好列举信息、分析票型和概率' },
  { code: 'suspicious', name: '疑心病重型', description: '对多数人都保持怀疑' },
  { code: 'team_player', name: '团结协作型', description: '更愿意跟随自己信任的队友' },
]

export async function fetchHomePageData(configApi, statsApi) {
  const [rolesRes, personalitiesRes, statsRes] = await Promise.all([
    configApi.getRoles(),
    configApi.getPersonalities(),
    statsApi.getOverview(),
  ])

  return {
    roles: Array.isArray(rolesRes.data) && rolesRes.data.length > 0 ? rolesRes.data : null,
    personalities: Array.isArray(personalitiesRes.data) && personalitiesRes.data.length > 0 ? personalitiesRes.data : null,
    stats: statsRes.data || null,
  }
}
