import { buildSeatModelMap, DEFAULT_MODELS, DEFAULT_ROLES } from '@/gameSetup'

export function sanitizeHumanSeats(humanSeats, totalPlayers) {
  return humanSeats.filter((seat) => seat <= totalPlayers)
}

export function toggleHumanSeatSelection(humanSeats, seat) {
  if (humanSeats.includes(seat)) {
    return humanSeats.filter((item) => item !== seat)
  }
  return [...humanSeats, seat]
}

export function validateGameSetup(roleCountValid, wolfCountValid, passwordError) {
  if (!roleCountValid) {
    return '角色数量不匹配，请调整配置'
  }
  if (!wolfCountValid) {
    return '狼人阵营人数过多，当前人数局不允许'
  }
  if (passwordError) {
    return passwordError
  }
  return ''
}

export function buildGameCreationPayload(config) {
  const seatModelMap = !config.aiConfig.randomModel
    ? buildSeatModelMap(config.seatModelMap)
    : {}

  return {
    total_players: config.totalPlayers,
    num_wolves: config.roleConfig.WOLF,
    role_config: config.roleConfig,
    human_seats: config.humanSeats,
    random_models: config.aiConfig.randomModel,
    seat_model_map: Object.keys(seatModelMap).length > 0 ? seatModelMap : null,
    god_mode: config.godMode.enabled
      ? {
          enabled: true,
          password: config.godMode.password,
        }
      : null,
  }
}

export async function loadSetupResources(configApi) {
  const snapshot = {
    roles: DEFAULT_ROLES,
    models: DEFAULT_MODELS,
  }

  const [rolesRes, modelsRes] = await Promise.all([
    configApi.getRoles(),
    configApi.getModels(),
  ])

  if (rolesRes.data && Array.isArray(rolesRes.data) && rolesRes.data.length > 0) {
    snapshot.roles = rolesRes.data
  }
  if (modelsRes.data && Array.isArray(modelsRes.data) && modelsRes.data.length > 0) {
    snapshot.models = modelsRes.data
  }

  return snapshot
}
