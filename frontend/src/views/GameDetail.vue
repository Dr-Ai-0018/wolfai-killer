<template>
  <div class="min-h-screen py-8 px-4">
    <div class="max-w-6xl mx-auto">
      <div class="flex items-center justify-between mb-8">
        <div>
          <router-link to="/history" class="text-gray-400 hover:text-white mb-2 inline-flex items-center">
            ← 返回列表
          </router-link>
          <h1 class="text-3xl font-bold text-white">对局详情</h1>
        </div>
        <div :class="[
          'px-4 py-2 rounded-xl text-lg font-semibold',
          game.winner_camp?.includes('狼人') ? 'bg-wolf-red/20 text-wolf-red' : 'bg-good-green/20 text-good-green'
        ]">
          {{ game.winner_camp || '进行中' }}
        </div>
      </div>

      <div class="grid md:grid-cols-3 gap-6 mb-8">
        <div class="glass rounded-xl p-4">
          <div class="text-gray-400 text-sm mb-1">游戏时长</div>
          <div class="text-2xl font-bold text-white">{{ formatDuration(game.duration) }}</div>
        </div>
        <div class="glass rounded-xl p-4">
          <div class="text-gray-400 text-sm mb-1">总回合</div>
          <div class="text-2xl font-bold text-white">{{ game.total_rounds || 0 }}</div>
        </div>
        <div class="glass rounded-xl p-4">
          <div class="text-gray-400 text-sm mb-1">玩家数</div>
          <div class="text-2xl font-bold text-white">{{ game.total_players }} ({{ game.num_humans }}真人)</div>
        </div>
      </div>

      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-xl font-semibold text-white mb-4">玩家列表</h2>
        <div class="grid md:grid-cols-4 gap-4">
          <div v-for="player in game.players" :key="player.seat"
               :class="[
                 'p-4 rounded-xl border',
                 player.alive ? 'bg-game-dark border-game-border' : 'bg-gray-800/50 border-gray-700'
               ]">
            <div class="flex items-center justify-between mb-2">
              <span class="text-2xl">{{ getRoleIcon(player.role) }}</span>
              <span :class="[
                'text-xs px-2 py-1 rounded',
                player.camp === '狼人阵营' ? 'bg-wolf-red/20 text-wolf-red' : 'bg-good-green/20 text-good-green'
              ]">
                {{ isWinner(player) ? '胜' : '败' }}
              </span>
            </div>
            <div class="text-white font-medium">{{ player.seat }}号 - {{ player.role }}</div>
            <div class="text-sm text-gray-400">{{ player.is_human ? '真人' : (player.personality_name || '智能玩家') }}</div>
            <div v-if="!player.alive" class="text-xs text-red-500 mt-1">已死亡</div>
          </div>
        </div>
      </div>

      <div class="glass rounded-2xl p-6">
        <h2 class="text-xl font-semibold text-white mb-4">公开局势摘要</h2>
        <div v-if="hasDaySummary" class="grid md:grid-cols-3 gap-4 mb-6">
          <div class="rounded-xl bg-game-dark/40 p-4">
            <div class="text-sm text-gray-400 mb-2">身份跳法</div>
            <div v-if="claimEntries.length > 0" class="space-y-2">
              <div v-for="entry in claimEntries" :key="entry.role" class="text-gray-200">
                {{ entry.role }}: {{ entry.seatsText }}
              </div>
            </div>
            <div v-else class="text-gray-500">无</div>
          </div>
          <div class="rounded-xl bg-game-dark/40 p-4">
            <div class="text-sm text-gray-400 mb-2">票型</div>
            <div v-if="voteCountEntries.length > 0" class="space-y-2">
              <div v-for="entry in voteCountEntries" :key="entry.seat" class="text-gray-200">
                {{ entry.seat }}号: {{ entry.count }}票
              </div>
            </div>
            <div v-else class="text-gray-500">无</div>
          </div>
          <div class="rounded-xl bg-game-dark/40 p-4">
            <div class="text-sm text-gray-400 mb-2">压力榜</div>
            <div v-if="pressureBoard.length > 0" class="space-y-2">
              <div v-for="item in pressureBoard" :key="item.seat" class="text-gray-200">
                {{ item.seat }}号: 点名{{ item.mentions }} / 票{{ item.votes }}
              </div>
            </div>
            <div v-else class="text-gray-500">无</div>
          </div>
        </div>

        <div class="mb-6 rounded-xl bg-game-dark/40 p-4">
          <div class="text-sm text-gray-400 mb-2">关键事件</div>
          <div v-if="publicRoleEvents.length > 0" class="space-y-2">
            <div v-for="(event, index) in publicRoleEvents" :key="`${index}-${event}`" class="rounded-lg bg-slate-950/40 p-3">
              <div class="text-gray-200">{{ event }}</div>
              <div v-if="explainPublicEvent(event)" class="mt-1 text-xs text-slate-400">
                {{ explainPublicEvent(event) }}
              </div>
            </div>
          </div>
          <div v-else class="text-gray-500">暂无关键角色事件</div>
        </div>

        <div class="mb-6 rounded-xl bg-game-dark/40 p-4">
          <div class="text-sm text-gray-400 mb-2">我的关键事件</div>
          <div v-if="playerEventCards.length > 0" class="grid md:grid-cols-2 gap-3">
            <div v-for="card in playerEventCards" :key="`${card.seat}-${card.role}`"
                 class="rounded-xl border border-game-border bg-slate-950/40 p-3">
              <div class="mb-2 flex items-center justify-between">
                <div class="text-white font-medium">{{ card.seat }}号 · {{ card.role }}</div>
                <div :class="[
                  'text-xs px-2 py-1 rounded',
                  card.isHuman ? 'bg-game-accent/20 text-game-accent-light' : 'bg-slate-700/50 text-slate-300'
                ]">
                  {{ card.isHuman ? '真人' : '智能玩家' }}
                </div>
              </div>
              <div v-if="card.events.length > 0" class="space-y-2">
                <div v-for="(event, index) in card.events" :key="`${card.seat}-${index}`" class="rounded-lg bg-black/20 p-2">
                  <div class="text-sm text-gray-200">{{ event }}</div>
                  <div v-if="explainPublicEvent(event)" class="mt-1 text-xs text-slate-400">
                    {{ explainPublicEvent(event) }}
                  </div>
                </div>
              </div>
              <div v-else class="text-sm text-gray-500">本局没有捕捉到公开关键事件</div>
            </div>
          </div>
          <div v-else class="text-gray-500">暂无可提炼的个人关键事件</div>
        </div>

        <h2 class="text-xl font-semibold text-white mb-4">游戏日志</h2>
        <div v-if="game.logs && game.logs.length > 0" class="space-y-2 max-h-96 overflow-y-auto">
          <div v-for="(log, index) in game.logs" :key="index"
               :class="['p-3 rounded-lg text-sm', getLogClass(log)]">
            <span v-if="log.seat" class="text-gray-400 mr-2">[{{ log.seat }}号]</span>
            <span class="text-gray-200">{{ log.content }}</span>
          </div>
        </div>
        <div v-else class="text-gray-400 text-center py-8">
          暂无日志记录（历史对局未保存日志）
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { statsApi } from '@/api'
import { buildPlayerEventCards, explainPublicEvent, extractPublicRoleEvents } from '@/gameReview'

const route = useRoute()
const game = ref({ players: [], logs: [], day_summary: null })

const daySummary = computed(() => game.value.day_summary || {})
const hasDaySummary = computed(() => !!game.value.day_summary)
const claimEntries = computed(() => {
  const claims = daySummary.value.claims || {}
  return Object.entries(claims)
    .filter(([, seats]) => Array.isArray(seats) && seats.length > 0)
    .map(([role, seats]) => ({
      role,
      seatsText: seats.map((seat) => `${seat}号`).join('、'),
    }))
})
const voteCountEntries = computed(() => {
  const counts = daySummary.value.vote_counts || {}
  return Object.entries(counts)
    .map(([seat, count]) => ({ seat: Number(seat), count: Number(count) }))
    .sort((a, b) => b.count - a.count || a.seat - b.seat)
})
const pressureBoard = computed(() => daySummary.value.pressure_board || [])
const publicRoleEvents = computed(() => extractPublicRoleEvents(game.value.logs || []))
const playerEventCards = computed(() => buildPlayerEventCards(game.value.players || [], game.value.logs || []))

const getRoleIcon = (role) => {
  const icons = { 
    '狼人': '🐺', '村民': '👨‍🌾', '预言家': '🔮', '女巫': '🧙‍♀️', '猎人': '🏹', '守卫': '🛡️',
    '狼王': '👑', '白狼王': '🐺', '狼美人': '💋', '丘比特': '💘', '白痴': '🤪', '长老': '👴',
    '圣徒': '⛪', '野孩子': '🧒', '共济会': '🤝', '被诅咒者': '🕯️', '受祝福者': '✨'
  }
  return icons[role] || '❓'
}

const formatDuration = (seconds) => {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}分${s}秒` : `${m}分钟`
}

// 判断玩家是否获胜
const isWinner = (player) => {
  if (!game.value.winner_camp) return false
  return player.camp === game.value.winner_camp
}

const getLogClass = (log) => {
  if (log.type === 'death') return 'bg-wolf-red/20'
  if (log.type === 'speech') return 'bg-game-dark/50'
  if (log.type === 'vote') return 'bg-blue-500/20'
  if (log.type === 'phase') return 'bg-purple-500/20'
  return 'bg-game-dark/30'
}

onMounted(async () => {
  try {
    const res = await statsApi.getGameDetail(route.params.gameId)
    game.value = res.data
    console.log('对局详情已加载', res.data)
  } catch (error) {
    console.error('加载对局详情失败', error)
  }
})
</script>
