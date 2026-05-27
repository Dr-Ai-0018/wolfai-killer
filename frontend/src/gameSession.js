import { nextTick } from 'vue'

import { buildActionRequiredSnapshot, buildConnectedSnapshot, buildStateSnapshot } from '@/gameRealtime'
import { buildGodModeDisplayState, fetchGodModeBundle } from '@/gameSpectator'
import { parseVoteSnapshot } from '@/gamePlay'
import { buildSpeechBubble, toggleAllowedSeat } from '@/gamePlayUi'

export function applyVoteSnapshot(gameLogs, dayCount, daySummary, currentVotes, voteCounts) {
  const snapshot = parseVoteSnapshot(gameLogs, dayCount, daySummary)
  currentVotes.value = snapshot.votes
  voteCounts.value = snapshot.counts
}

export function showSpeechBubbleForLog(speechBubble, latestSpeaker, seat, content) {
  speechBubble.value = buildSpeechBubble(seat, content)
  latestSpeaker.value = seat
  setTimeout(() => {
    speechBubble.value = { show: false, seat: null, content: '' }
  }, 3000)
}

export function scrollLogToBottom(logContainer) {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

export async function refreshGodModeBundle(gameApi, gameId, password, godModeLogs, godModePlayers, logContainer) {
  const bundle = await fetchGodModeBundle(gameApi, gameId, password)
  godModeLogs.value = bundle.logs
  godModePlayers.value = bundle.players
  scrollLogToBottom(logContainer)
}

export function closeGodModePanel(godModeActive, godModeLogs, godModePlayers, showGodModeModal) {
  const nextState = buildGodModeDisplayState(false)
  godModeActive.value = nextState.active
  godModeLogs.value = nextState.logs
  godModePlayers.value = nextState.players
  showGodModeModal.value = nextState.showPasswordModal
}

export function applyConnectedEvent(data, refs) {
  const { wsConnected, mySeat, myRole, gameState, players, gameLogs, godModeEnabled, pendingAction, logContainer } = refs
  wsConnected.value = true
  mySeat.value = data.seat
  myRole.value = data.role

  if (data.game_state) {
    const snapshot = buildConnectedSnapshot(data, mySeat.value)
    gameState.value = snapshot.gameState
    players.value = snapshot.players
    gameLogs.value = snapshot.logs
    godModeEnabled.value = snapshot.godModeEnabled
    pendingAction.value = snapshot.pendingAction
  }

  scrollLogToBottom(logContainer)
}

export function applyStateEvent(data, refs) {
  const {
    mySeat,
    gameState,
    players,
    gameLogs,
    pendingAction,
    selectedAllowedVoters,
    timer,
    currentVotes,
    voteCounts,
    godModeActive,
    loadGodModeData,
    speechBubble,
    latestSpeaker,
    logContainer,
  } = refs

  const snapshot = buildStateSnapshot(data, mySeat.value)
  gameState.value = snapshot.gameState
  players.value = snapshot.players

  if (data.logs) {
    const oldLogsCount = gameLogs.value.length
    gameLogs.value = data.logs
    scrollLogToBottom(logContainer)

    if (data.logs.length > oldLogsCount) {
      const newLogs = data.logs.slice(oldLogsCount)
      for (const log of newLogs) {
        if (log.type === 'speech' && log.seat) {
          showSpeechBubbleForLog(speechBubble, latestSpeaker, log.seat, log.content)
          break
        }
      }
    }

    if (data.phase === 'vote') {
      applyVoteSnapshot(gameLogs.value, gameState.value.day_count, gameState.value.day_summary, currentVotes, voteCounts)
    } else {
      currentVotes.value = {}
      voteCounts.value = {}
    }
  }

  if (godModeActive.value) {
    loadGodModeData()
  }

  if (snapshot.pendingAction) {
    pendingAction.value = snapshot.pendingAction
    selectedAllowedVoters.value = []
    timer.value = snapshot.timer
  } else {
    pendingAction.value = null
    selectedAllowedVoters.value = []
  }
}

export function applyActionRequiredEvent(data, mySeat, pendingAction, selectedAllowedVoters, timer) {
  const snapshot = buildActionRequiredSnapshot(data, mySeat.value)
  if (!snapshot) return
  pendingAction.value = snapshot.pendingAction
  selectedAllowedVoters.value = []
  timer.value = snapshot.timer
}

export function toggleScapegoatSeatSelection(pendingAction, selectedAllowedVoters, seat) {
  if (!pendingAction.value || pendingAction.value.action_type !== 'scapegoat') return
  const candidates = pendingAction.value.options?.candidates || []
  selectedAllowedVoters.value = toggleAllowedSeat(selectedAllowedVoters.value, candidates, seat)
}
