const PHASE_TEXT = {
  waiting: '等待开始',
  night: '夜晚阶段',
  day: '白天阶段',
  vote: '投票阶段',
  ended: '游戏结束',
}

const LOG_CLASSES = {
  death: 'bg-gradient-to-r from-red-950/60 to-red-900/30 border border-red-800/50',
  speech: 'bg-slate-900/40',
  vote: 'bg-blue-950/40 border border-blue-800/30',
  phase: 'bg-gradient-to-r from-violet-950/50 to-purple-900/30 border border-violet-700/30',
  system: 'bg-slate-800/30',
  end: 'bg-gradient-to-r from-amber-950/50 to-yellow-900/30 border border-amber-700/40',
  reveal: 'bg-gradient-to-r from-emerald-950/50 to-green-900/30 border border-emerald-700/30',
  eliminate: 'border border-red-700/40',
  hunter: 'bg-orange-950/40 border border-orange-700/30',
}

const LOG_TEXT_CLASSES = {
  phase: 'text-violet-300 font-medium',
  system: 'text-slate-400',
  death: 'text-red-300',
  end: 'text-amber-300 font-bold',
}

const ROLE_ICONS = {
  狼人: '🐺',
  村民: '👨‍🌾',
  预言家: '🔮',
  女巫: '🧙‍♀️',
  猎人: '🏹',
  守卫: '🛡️',
  狐狸: '🦊',
  天使: '😇',
  替罪羊: '🐐',
  丘比特: '💘',
  白痴: '🤪',
  长老: '👴',
  圣徒: '⛪',
  野孩子: '🧒',
  共济会: '🤝',
  被诅咒者: '🕯️',
  受祝福者: '✨',
}

const ROLE_ANNOUNCEMENT_ICONS = {
  守卫: '🛡️',
  狼人: '🐺',
  预言家: '🔮',
  女巫: '🧙‍♀️',
  猎人: '🏹',
  狐狸: '🦊',
  天使: '😇',
  替罪羊: '🐐',
  丘比特: '💘',
  野孩子: '🧒',
}

export function getPhaseText(phase) {
  return PHASE_TEXT[phase] || phase
}

export function getLogClass(logType) {
  return LOG_CLASSES[logType] || 'bg-slate-800/30'
}

export function getLogTextClass(logType) {
  return LOG_TEXT_CLASSES[logType] || 'text-slate-300'
}

export function getPlayerPositionStyle(index, total) {
  const angle = (index * 2 * Math.PI / total) - Math.PI / 2
  const radius = 250
  const x = 300 + radius * Math.cos(angle)
  const y = 300 + radius * Math.sin(angle)
  return { left: `${x}px`, top: `${y}px` }
}

export function getPlayerCenterCoords(seat, totalPlayers) {
  const index = seat - 1
  const total = totalPlayers || 12
  const angle = (index * 2 * Math.PI / total) - Math.PI / 2
  const radius = 250
  return {
    x: 300 + radius * Math.cos(angle),
    y: 300 + radius * Math.sin(angle),
  }
}

export function getVoteLineCoords(voter, target, totalPlayers) {
  const from = getPlayerCenterCoords(Number(voter), totalPlayers)
  const to = getPlayerCenterCoords(Number(target), totalPlayers)
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.sqrt(dx * dx + dy * dy)
  const ratio = 45 / len
  return {
    x1: from.x + dx * ratio,
    y1: from.y + dy * ratio,
    x2: to.x - dx * ratio,
    y2: to.y - dy * ratio,
  }
}

export function buildSpeechBubble(seat, content) {
  return {
    show: true,
    seat,
    content: `${content.substring(0, 30)}...`,
  }
}

export function getPlayerIcon(player, mySeat) {
  if (!player.alive) return '💀'
  if (player.seat === mySeat) return '👤'
  return '🤖'
}

export function getPlayerBorderClass(player, mySeat) {
  if (!player.alive) return 'border-gray-600'
  if (player.seat === mySeat) return 'border-game-accent'
  return 'border-game-border'
}

export function getRoleIcon(role) {
  return ROLE_ICONS[role] || '❓'
}

export function getRoleAnnouncementIcon(role) {
  return ROLE_ANNOUNCEMENT_ICONS[role] || '🌙'
}

export function formatCountdown(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function canSelectTarget(player, mySeat, pendingAction, needsTargetSelection) {
  if (!needsTargetSelection) return false
  if (!player.alive && pendingAction?.action_type !== 'hunter') return false
  if (player.seat === mySeat && pendingAction?.action_type !== 'guard') return false
  const candidates = pendingAction?.options?.candidates || []
  if (candidates.length > 0 && !candidates.includes(player.seat)) return false
  return true
}

export function toggleAllowedSeat(selectedSeats, candidates, seat) {
  if (!candidates.includes(seat)) {
    return selectedSeats
  }
  if (selectedSeats.includes(seat)) {
    return selectedSeats.filter((item) => item !== seat)
  }
  return [...selectedSeats, seat]
}
