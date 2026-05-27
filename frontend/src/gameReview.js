export const PUBLIC_ROLE_EVENT_PATTERNS = [
  '翻牌为白痴',
  '无投票权',
  '因情侣殉情而死亡',
  '受祝福者抵挡了第一次狼人袭击',
  '长老承受了第一次狼人袭击',
  '长老以非狼人袭击的方式死亡',
  '圣徒被公投出局后发动反噬',
  '天使在开局阶段达成了自己的死亡胜利条件',
  '替罪羊替死出局',
  '替罪羊指定下一天仅有',
]

export const extractPublicRoleEvents = (logs, { limit } = {}) => {
  const events = (Array.isArray(logs) ? logs : [])
    .filter((log) => {
      if (log && log.is_public === false) return false
      const content = String(log?.content || '')
      return PUBLIC_ROLE_EVENT_PATTERNS.some((pattern) => content.includes(pattern))
    })
    .map((log) => String(log.content || ''))

  return typeof limit === 'number' ? events.slice(-limit) : events
}

export const explainPublicEvent = (event) => {
  if (!event) return ''
  if (event.includes('翻牌为白痴')) return '这意味着该玩家白天被票出时没有真正出局，但后续将失去投票权。'
  if (event.includes('无投票权')) return '这说明白痴翻牌后的代价已经生效，后续白天只能发言不能投票。'
  if (event.includes('因情侣殉情而死亡')) return '这代表丘比特连线已经产生连锁后果，一名情侣死亡后另一名被同步带走。'
  if (event.includes('受祝福者抵挡了第一次狼人袭击')) return '这说明一次关键狼刀被角色被动能力抵消，场上有效存活人数因此改变。'
  if (event.includes('长老承受了第一次狼人袭击')) return '这说明长老的额外生存层数被触发，狼人夜刀没有直接拿到击杀收益。'
  if (event.includes('长老以非狼人袭击的方式死亡')) return '这通常会让好人神职能力失效，属于高影响力的局势转折点。'
  if (event.includes('圣徒被公投出局后发动反噬')) return '这说明白天公投不仅出了目标，还额外带走了一名最后投票者，票型价值被放大了。'
  if (event.includes('天使在开局阶段达成了自己的死亡胜利条件')) return '这代表第三方角色在首夜或首日通过死亡直接完成了独立胜利，整局胜负会立刻改写。'
  if (event.includes('替罪羊替死出局')) return '这说明平票没有按常规流掉，而是由替罪羊承担了出局结果，白天博弈被强行改线。'
  if (event.includes('替罪羊指定下一天仅有')) return '这代表下一天的投票权被大幅收缩，后续票型不再由全场共同决定。'
  return ''
}

export const buildPlayerEventCards = (players, logs) => {
  const cards = (Array.isArray(players) ? players : []).map((player) => ({
    seat: player.seat,
    role: player.role,
    isHuman: !!player.is_human,
    events: [],
  }))

  const publicEvents = extractPublicRoleEvents(logs)
  for (const event of publicEvents) {
    for (const card of cards) {
      if (event.includes(`${card.seat}号`)) {
        card.events.push(event)
      }
    }
  }

  return cards.filter((card) => card.events.length > 0)
}
