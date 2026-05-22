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
            <div class="text-sm text-gray-400">{{ player.is_human ? '真人' : (player.personality_name || 'AI') }}</div>
            <div v-if="!player.alive" class="text-xs text-red-500 mt-1">已死亡</div>
          </div>
        </div>
      </div>

      <div class="glass rounded-2xl p-6">
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
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { statsApi } from '@/api'

const route = useRoute()
const game = ref({ players: [], logs: [] })

const getRoleIcon = (role) => {
  const icons = { 
    '狼人': '🐺', '村民': '👨‍🌾', '预言家': '🔮', '女巫': '🧙‍♀️', '猎人': '🏹', '守卫': '🛡️',
    '狼王': '👑', '白狼王': '🐺', '狼美人': '💋', '丘比特': '💘', '白痴': '🤪', '长老': '👴'
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
    console.log('Game detail loaded:', res.data)
  } catch (error) {
    console.error('Failed to load game detail:', error)
  }
})
</script>
