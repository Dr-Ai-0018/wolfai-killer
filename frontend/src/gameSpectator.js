export async function fetchAfterlifeActions(api, gameId) {
  const res = await api.getPhantomActions(gameId)
  if (!res.data.available) {
    return []
  }
  return res.data.phantom_actions || []
}

export async function fetchGodModeBundle(api, gameId, password) {
  const [logsRes, playersRes] = await Promise.all([
    api.getGodModeLogs(gameId, password),
    api.getGodModePlayers(gameId, password),
  ])
  return {
    logs: logsRes.data.logs || [],
    players: playersRes.data || [],
  }
}

export function buildGodModeDisplayState(active) {
  if (active) {
    return {
      active: true,
      logs: [],
      players: [],
      showPasswordModal: false,
    }
  }
  return {
    active: false,
    logs: [],
    players: [],
    showPasswordModal: false,
  }
}
