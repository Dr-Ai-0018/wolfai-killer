const DEFAULT_DAY_SUMMARY = {
  day: 0,
  phase: 'waiting',
  claims: {},
  vote_map: {},
  vote_counts: {},
  pressure_board: [],
}

export function buildDaySummary(daySummary, dayCount, phase) {
  return daySummary || {
    ...DEFAULT_DAY_SUMMARY,
    day: dayCount,
    phase,
  }
}

export function buildPendingAction(seat, actionType, options) {
  if (!seat || !actionType) {
    return null
  }
  return {
    seat,
    action_type: actionType,
    options: options || {},
    message: options?.message || '请行动',
  }
}

export function buildPlayStateSnapshot(source, overrides = {}) {
  return {
    phase: source.phase,
    day_count: source.day_count,
    night_count: source.night_count,
    paused: overrides.paused ?? source.paused ?? false,
    winner: overrides.winner ?? source.winner ?? null,
    waiting_for_human: source.waiting_for_human,
    human_action_type: source.human_action_type,
    human_action_options: source.human_action_options || {},
    current_action_role: source.current_action_role,
    current_action_message: source.current_action_message,
    day_summary: buildDaySummary(source.day_summary, source.day_count, source.phase),
  }
}

export function parseVoteSnapshot(logs, dayCount, daySummary) {
  const summaryVoteMap = daySummary?.vote_map || {}
  const summaryVoteCounts = daySummary?.vote_counts || {}
  if (Object.keys(summaryVoteMap).length > 0 || Object.keys(summaryVoteCounts).length > 0) {
    return {
      votes: Object.fromEntries(
        Object.entries(summaryVoteMap).map(([voter, target]) => [Number(voter), Number(target)]),
      ),
      counts: Object.fromEntries(
        Object.entries(summaryVoteCounts).map(([target, count]) => [Number(target), Number(count)]),
      ),
    }
  }

  const votes = {}
  const counts = {}
  for (const log of logs) {
    if (log.type !== 'vote' || log.day !== dayCount) {
      continue
    }
    const match = log.content.match(/(\d+)号投给了(\d+)号/)
    if (!match) {
      continue
    }
    const voter = Number(match[1])
    const target = Number(match[2])
    votes[voter] = target
    counts[target] = (counts[target] || 0) + 1
  }
  return { votes, counts }
}
