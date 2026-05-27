import { buildPendingAction, buildPlayStateSnapshot } from '@/gamePlay'

export function buildConnectedSnapshot(data, mySeat) {
  const gameState = buildPlayStateSnapshot(data.game_state, { paused: false, winner: null })
  return {
    gameState,
    players: data.game_state.players,
    logs: data.game_state.logs || [],
    godModeEnabled: data.game_state.god_mode_enabled || false,
    pendingAction: data.game_state.waiting_for_human === mySeat
      ? buildPendingAction(mySeat, data.game_state.human_action_type, data.game_state.human_action_options)
      : null,
  }
}

export function buildStateSnapshot(data, mySeat) {
  const pendingAction = data.waiting_for_human === mySeat && data.human_action_type
    ? buildPendingAction(mySeat, data.human_action_type, data.human_action_options)
    : null

  return {
    gameState: buildPlayStateSnapshot(data),
    players: data.players,
    pendingAction,
    timer: data.human_action_options?.timeout || 120,
  }
}

export function buildActionRequiredSnapshot(data, mySeat) {
  if (data.seat !== mySeat) {
    return null
  }
  return {
    pendingAction: buildPendingAction(data.seat, data.action_type, data.options),
    timer: data.timeout || 120,
  }
}

export function applyRoleResult(roleState, data, type) {
  if (!roleState) {
    return null
  }
  if (type === 'seer') {
    return {
      ...roleState,
      seer_results: {
        ...(roleState.seer_results || {}),
        [data.target]: data.result,
      },
    }
  }
  const nextFoxChecks = {
    ...(roleState.fox_checks || {}),
    [data.target]: data.result,
  }
  return {
    ...roleState,
    fox_checks: nextFoxChecks,
    fox_power_active: data.result === '没有狼人' ? false : roleState.fox_power_active,
  }
}

export async function fetchInitialPlayerContext(api, gameId) {
  const playersRes = await api.getPlayers(gameId)
  const players = playersRes.data
  const humanPlayer = players.find((player) => player.is_human)
  if (!humanPlayer) {
    return { players, mySeat: null, myRole: null }
  }

  const viewRes = await api.getPlayerView(gameId, humanPlayer.seat)
  return {
    players,
    mySeat: humanPlayer.seat,
    myRole: viewRes.data,
  }
}
