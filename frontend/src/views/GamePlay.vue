<template>
  <div class="min-h-screen flex relative overflow-hidden">
    <!-- Night Overlay with Breathing Effect -->
    <transition name="night-fade">
      <div v-if="gameState.phase === 'night'" 
           class="fixed inset-0 z-40 pointer-events-none night-overlay">
        <div class="absolute inset-0 bg-black/90 animate-night-breathe"></div>
        <!-- Starry effect -->
        <div class="absolute inset-0 overflow-hidden">
          <div v-for="i in 20" :key="i" 
               class="absolute w-1 h-1 bg-white/30 rounded-full animate-twinkle"
               :style="{
                 left: `${Math.random() * 100}%`,
                 top: `${Math.random() * 100}%`,
                 animationDelay: `${Math.random() * 3}s`
               }"></div>
        </div>
      </div>
    </transition>

    <!-- Role Action Announcement Overlay -->
    <transition name="announce-fade">
      <div v-if="gameState.current_action_role" 
           class="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
        <div class="text-center animate-role-announce">
          <div class="text-6xl mb-6">{{ getRoleAnnouncementIcon(gameState.current_action_role) }}</div>
          <h2 class="text-4xl font-bold text-white mb-4 text-shadow-lg">
            {{ gameState.current_action_message }}
          </h2>
          <div class="w-24 h-1 bg-gradient-to-r from-transparent via-game-accent to-transparent mx-auto animate-pulse"></div>
        </div>
      </div>
    </transition>
    <!-- Left Panel - Game Log -->
    <div class="w-80 flex-shrink-0 glass border-r border-game-border flex flex-col h-screen">
      <div class="p-4 border-b border-game-border flex-shrink-0">
        <h2 class="text-lg font-semibold text-white flex items-center">
          <span :class="['w-2 h-2 rounded-full mr-2', wsConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500']"></span>
          游戏记录
        </h2>
      </div>
      
      <div class="flex-1 min-h-0 overflow-y-auto p-3 space-y-2" ref="logContainer">
        <div v-for="(log, index) in displayLogs" :key="index"
             :class="['rounded-xl text-sm transition-all', getLogClass(log)]">
          <!-- Phase/System logs -->
          <div v-if="log.type === 'phase' || log.type === 'system'" class="px-4 py-2 text-center">
            <span :class="getLogTextClass(log)">{{ log.content }}</span>
          </div>
          
          <!-- Death logs -->
          <div v-else-if="log.type === 'death'" class="px-4 py-3 flex items-center gap-3">
            <span class="text-2xl">💀</span>
            <span class="text-red-300 font-medium">{{ log.content }}</span>
          </div>
          
          <!-- Speech logs with avatar style -->
          <div v-else-if="log.type === 'speech'" class="p-3">
            <div class="flex items-start gap-3">
              <div class="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {{ log.seat }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-violet-400 text-xs font-medium">{{ log.seat }}号玩家</span>
                  <span class="text-slate-600 text-xs">发言</span>
                </div>
                <div class="bg-slate-800/50 rounded-xl rounded-tl-none px-3 py-2 text-slate-200 leading-relaxed">
                  {{ log.content }}
                </div>
              </div>
            </div>
          </div>
          
          <!-- Vote logs -->
          <div v-else-if="log.type === 'vote'" class="px-4 py-2 flex items-center gap-2">
            <span class="text-blue-400">🗳️</span>
            <span class="text-blue-300">{{ log.content }}</span>
          </div>
          
          <!-- Eliminate logs -->
          <div v-else-if="log.type === 'eliminate'" class="px-4 py-3 flex items-center gap-3 bg-gradient-to-r from-red-900/40 to-transparent">
            <span class="text-2xl">⚔️</span>
            <span class="text-red-300 font-semibold">{{ log.content }}</span>
          </div>
          
          <!-- End/Reveal logs -->
          <div v-else-if="log.type === 'end' || log.type === 'reveal'" class="px-4 py-3">
            <div class="flex items-center gap-2">
              <span class="text-xl">{{ log.type === 'end' ? '🏆' : '🎭' }}</span>
              <span :class="log.type === 'end' ? 'text-yellow-300 font-bold' : 'text-emerald-300'">{{ log.content }}</span>
            </div>
          </div>
          
          <!-- God mode logs -->
          <div v-else-if="!log.is_public" class="px-4 py-2 border-l-2 border-yellow-500">
            <span class="text-yellow-400 text-xs mr-2">👁️</span>
            <span class="text-yellow-200/80">{{ log.content }}</span>
          </div>
          
          <!-- Default -->
          <div v-else class="px-4 py-2">
            <span class="text-slate-300">{{ log.content }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Center - Player Circle -->
    <div class="flex-1 relative overflow-hidden">
      <!-- Phase Header -->
      <div class="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
        <div class="glass rounded-full px-6 py-2 flex items-center space-x-4">
          <span :class="['w-3 h-3 rounded-full', gameState.phase === 'night' ? 'bg-purple-500' : 'bg-yellow-500']"></span>
          <span class="text-white font-medium">
            {{ phaseText }}
          </span>
          <span class="text-gray-400">|</span>
          <span class="text-game-accent-light">
            第 {{ gameState.day_count }} 天
          </span>
        </div>
      </div>

      <!-- Controls -->
      <div class="absolute top-4 right-4 z-10 flex items-center space-x-4">
        <!-- 上帝模式开关 -->
        <button v-if="godModeEnabled"
                @click="toggleGodMode"
                :class="[
                  'glass px-4 py-2 rounded-xl transition-colors',
                  godModeActive ? 'bg-yellow-600 text-white' : 'text-gray-400 hover:text-white'
                ]">
          👁️ {{ godModeActive ? '关闭上帝' : '上帝模式' }}
        </button>
        <button v-if="gameState.phase !== 'ended' && gameState.phase !== 'waiting'"
                @click="togglePause"
                class="glass px-4 py-2 rounded-xl text-white hover:bg-game-accent transition-colors">
          {{ gameState.paused ? '▶️ 继续' : '⏸️ 暂停' }}
        </button>
        <div class="glass rounded-xl px-4 py-2 text-2xl font-bold text-white">
          {{ formatTime(timer) }}
        </div>
      </div>

      <!-- Player Circle -->
      <div class="absolute inset-0 flex items-center justify-center">
        <div class="relative w-[600px] h-[600px]">
          <!-- Vote Arrows SVG -->
          <svg v-if="gameState.phase === 'vote' && Object.keys(currentVotes).length > 0" 
               class="absolute inset-0 w-full h-full pointer-events-none z-10">
            <defs>
              <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#60a5fa" />
              </marker>
            </defs>
            <line v-for="(target, voter) in currentVotes" :key="`vote-${voter}-${target}`"
                  :x1="getVoteLineCoords(voter, target).x1"
                  :y1="getVoteLineCoords(voter, target).y1"
                  :x2="getVoteLineCoords(voter, target).x2"
                  :y2="getVoteLineCoords(voter, target).y2"
                  stroke="#60a5fa" 
                  stroke-width="2"
                  stroke-dasharray="5,5"
                  marker-end="url(#arrowhead)"
                  class="vote-arrow" />
          </svg>
          
          <!-- Players -->
          <div v-for="(player, index) in players" :key="player.seat"
               :style="getPlayerPosition(index, players.length)"
               class="absolute transform -translate-x-1/2 -translate-y-1/2 z-20">
            
            <!-- Vote Count Badge -->
            <div v-if="gameState.phase === 'vote' && voteCounts[player.seat]" 
                 class="absolute -top-2 -right-2 w-6 h-6 bg-red-500 rounded-full flex items-center justify-center text-white text-xs font-bold z-30 animate-bounce">
              {{ voteCounts[player.seat] }}
            </div>
            
            <!-- Speech Bubble -->
            <transition name="bubble">
              <div v-if="speechBubble.show && speechBubble.seat === player.seat"
                   class="absolute -top-16 left-1/2 -translate-x-1/2 bg-white text-gray-800 px-3 py-2 rounded-xl text-xs max-w-32 shadow-lg z-40">
                <div class="truncate">{{ speechBubble.content }}</div>
                <div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-white"></div>
              </div>
            </transition>
            
            <div :class="[
                   'w-20 h-20 rounded-full flex flex-col items-center justify-center cursor-pointer transition-all overflow-hidden',
                   player.alive ? 'bg-game-card border-2 shadow-lg' : 'bg-gray-800 opacity-50 grayscale',
                   getPlayerBorderClass(player),
                   selectedTarget === player.seat ? 'ring-4 ring-game-accent scale-110' : '',
                   gameState.waiting_for_human === player.seat ? 'ring-4 ring-yellow-500 animate-pulse' : '',
                   latestSpeaker === player.seat ? 'ring-4 ring-violet-500' : ''
                 ]"
                 @click="selectTarget(player)">
              <img v-if="player.avatar" 
                   :src="getAvatarUrl(player.avatar)" 
                   class="w-full h-full object-cover"
                   @error="handleImageError" />
              <div v-else class="text-2xl">{{ getPlayerIcon(player) }}</div>
            </div>
            <div class="text-center mt-2">
              <div class="text-sm text-white font-medium">{{ player.seat }}号</div>
              <div v-if="!player.alive" class="text-xs text-red-400">💀 出局</div>
              <div v-else-if="player.seat === mySeat" class="text-xs text-game-accent-light font-medium">你</div>
            </div>
          </div>
          
          <!-- Center Vote Summary -->
          <div v-if="gameState.phase === 'vote' && Object.keys(currentVotes).length > 0"
               class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-slate-900/90 backdrop-blur-sm px-6 py-4 rounded-2xl border border-slate-700">
            <div class="text-center">
              <div class="text-sm text-slate-400 mb-2">当前票数</div>
              <div class="flex flex-wrap gap-2 justify-center">
                <div v-for="(count, target) in voteCounts" :key="target"
                     class="px-3 py-1 bg-blue-600/30 border border-blue-500/50 rounded-full text-blue-300 text-sm">
                  {{ target }}号: {{ count }}票
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Start Game Button (if waiting) -->
      <div v-if="gameState.phase === 'waiting'" class="absolute bottom-8 left-1/2 transform -translate-x-1/2">
        <button @click="startGame" 
                class="px-8 py-4 bg-game-accent hover:bg-game-accent-light rounded-xl text-white text-xl font-bold transition-colors">
          开始游戏
        </button>
      </div>

      <!-- Winner Announcement with Afterlife Review -->
      <div v-if="gameState.winner" class="absolute inset-0 flex items-center justify-center bg-black/80 z-20">
        <div class="glass rounded-2xl p-8 text-center max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
          <div class="text-6xl mb-4">
            {{ gameState.winner.includes('狼人') ? '🐺' : '🎉' }}
          </div>
          <h2 class="text-3xl font-bold text-white mb-4">游戏结束</h2>
          <p class="text-2xl mb-6" :class="gameState.winner.includes('狼人') ? 'text-red-400' : 'text-green-400'">
            {{ gameState.winner }} 获胜！
          </p>

          <div class="mb-6 rounded-xl border border-game-border bg-slate-950/40 p-4 text-left">
            <div class="mb-2 text-sm text-slate-400">我的关键事件</div>
            <div v-if="myPublicRoleEvents.length > 0" class="space-y-2">
              <div v-for="(event, index) in myPublicRoleEvents" :key="`${index}-${event}`"
                   class="rounded-lg bg-black/30 px-3 py-2">
                <div class="text-sm text-slate-200">{{ event }}</div>
                <div v-if="explainPublicEvent(event)" class="mt-1 text-xs text-slate-400">
                  {{ explainPublicEvent(event) }}
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-slate-500">本局没有与你直接相关的公开关键事件</div>
          </div>
          
          <!-- Afterlife Review Button -->
          <button v-if="!showAfterlife" @click="loadAfterlifeReview"
                  class="mb-6 px-6 py-3 bg-purple-600 hover:bg-purple-500 rounded-xl text-white font-medium transition-colors">
            👻 查看冥界复盘
          </button>
          
          <!-- Afterlife Review Content -->
          <div v-if="showAfterlife && phantomActions.length > 0" 
               class="mt-4 p-4 bg-purple-900/30 rounded-xl border border-purple-700 text-left">
            <h3 class="text-lg font-bold text-purple-300 mb-4 flex items-center">
              <span class="text-2xl mr-2">👻</span>
              冥界复盘 - 如果他们没有死...
            </h3>
            <div class="space-y-3">
              <div v-for="(action, index) in phantomActions" :key="index"
                   class="p-3 bg-black/30 rounded-lg border-l-4 border-purple-500">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-purple-400 font-medium">
                    第{{ action.night }}夜 - {{ action.role }}({{ action.seat }}号)
                  </span>
                </div>
                <p class="text-gray-300">{{ action.decision }}</p>
              </div>
            </div>
          </div>
          <div v-else-if="showAfterlife" class="mt-4 text-gray-500">
            本局游戏没有冥界记录
          </div>
          
          <button @click="$router.push('/')" 
                  class="mt-6 px-8 py-3 bg-game-accent hover:bg-game-accent-light rounded-xl text-white font-medium transition-colors">
            返回首页
          </button>
        </div>
      </div>

      <!-- God Mode Password Modal -->
      <div v-if="showGodModeModal" class="absolute inset-0 flex items-center justify-center bg-black/70 z-30">
        <div class="glass rounded-2xl p-6 w-80">
          <h3 class="text-xl font-bold text-white mb-4 flex items-center">
            👁️ 上帝模式验证
          </h3>
          <p class="text-sm text-gray-400 mb-4">
            请输入上帝模式密码以查看所有隐藏信息
          </p>
          <input type="password" v-model="godModePassword" 
                 placeholder="输入密码..."
                 @keyup.enter="verifyGodModePassword"
                 class="w-full bg-game-dark border border-game-border rounded-lg px-4 py-3 text-white 
                        focus:border-game-accent focus:outline-none mb-4">
          <div class="flex space-x-3">
            <button @click="showGodModeModal = false; godModePassword = ''" 
                    class="flex-1 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-white">
              取消
            </button>
            <button @click="verifyGodModePassword" 
                    class="flex-1 py-2 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-white">
              确认
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Panel - Player Info & Actions -->
    <div class="w-80 flex-shrink-0 glass border-l border-game-border flex flex-col h-screen">
      <!-- My Role Card -->
      <div v-if="myRole" class="p-4 border-b border-game-border flex-shrink-0">
        <div class="bg-game-accent/20 rounded-xl p-4">
          <div class="flex items-center mb-3">
            <span class="text-4xl mr-3">{{ getRoleIcon(myRole.role) }}</span>
            <div>
              <h3 class="text-xl font-bold text-white">{{ myRole.role }}</h3>
              <p :class="['text-sm', myRole.camp === '好人阵营' ? 'text-green-400' : 'text-red-400']">
                {{ myRole.camp }}
              </p>
            </div>
          </div>
          
          <!-- Role-specific info -->
          <div v-if="myRole.role === '女巫'" class="text-sm text-gray-300 space-y-1">
            <p>解药：{{ myRole.has_heal ? '✅ 有' : '❌ 无' }}</p>
            <p>毒药：{{ myRole.has_poison ? '✅ 有' : '❌ 无' }}</p>
          </div>
          <div v-if="myRole.role === '预言家' && myRole.seer_results" class="text-sm text-gray-300">
            <p class="font-medium mb-1">查验结果：</p>
            <div v-for="(result, seat) in myRole.seer_results" :key="seat">
              {{ seat }}号：<span :class="result === '狼人' ? 'text-red-400' : 'text-green-400'">{{ result }}</span>
            </div>
          </div>
          <div v-if="myRole.role === '狐狸'" class="text-sm text-gray-300 space-y-1">
            <p>能力状态：{{ myRole.fox_power_active ? '✅ 可继续嗅探' : '❌ 已失效' }}</p>
            <div v-if="myRole.fox_checks && Object.keys(myRole.fox_checks).length > 0">
              <p class="font-medium mb-1">嗅探结果：</p>
              <div v-for="(result, seat) in myRole.fox_checks" :key="seat">
                围绕 {{ seat }}号：<span :class="result === '有狼人' ? 'text-red-400' : 'text-green-400'">{{ result }}</span>
              </div>
            </div>
          </div>
          <div v-if="myRole.role === '天使'" class="text-sm text-gray-300 space-y-1">
            <p>开局胜利条件：{{ myRole.angel_active ? '✅ 仍可触发' : '❌ 已失效' }}</p>
          </div>
          <div v-if="myRole.role === '长老'" class="text-sm text-gray-300 space-y-1">
            <p>剩余生命层数：{{ myRole.elder_lives ?? 0 }}</p>
          </div>
        </div>
      </div>

      <!-- Action Panel -->
      <div class="flex-1 min-h-0 overflow-y-auto p-4">
        <div class="mb-6 rounded-2xl border border-game-border bg-slate-950/40 p-4">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-white">公开局势</h3>
            <span class="text-xs text-slate-400">第{{ displayDaySummary.day || gameState.day_count }}天</span>
          </div>

          <div class="space-y-4 text-sm">
            <div>
              <div class="mb-2 text-slate-400">身份跳法</div>
              <div v-if="claimEntries.length > 0" class="flex flex-wrap gap-2">
                <div v-for="entry in claimEntries" :key="entry.role"
                     class="rounded-full border border-violet-700/40 bg-violet-950/40 px-3 py-1 text-violet-200">
                  {{ entry.role }}: {{ entry.seatsText }}
                </div>
              </div>
              <div v-else class="text-slate-500">暂无公开跳身份</div>
            </div>

            <div>
              <div class="mb-2 text-slate-400">票型</div>
              <div v-if="voteCountEntries.length > 0" class="flex flex-wrap gap-2">
                <div v-for="entry in voteCountEntries" :key="entry.seat"
                     class="rounded-full border border-blue-700/40 bg-blue-950/40 px-3 py-1 text-blue-200">
                  {{ entry.seat }}号 {{ entry.count }}票
                </div>
              </div>
              <div v-else class="text-slate-500">当前还没有公开投票</div>
            </div>

            <div>
              <div class="mb-2 text-slate-400">压力榜</div>
              <div v-if="pressureBoard.length > 0" class="space-y-2">
                <div v-for="item in pressureBoard" :key="item.seat"
                     class="flex items-center justify-between rounded-xl bg-slate-900/60 px-3 py-2">
                  <div class="text-slate-200">
                    {{ item.seat }}号
                    <span v-if="item.claimed_role" class="ml-2 text-xs text-violet-300">跳{{ item.claimed_role }}</span>
                  </div>
                  <div class="text-xs text-slate-400">
                    发言点名 {{ item.mentions }} / 票数 {{ item.votes }}
                  </div>
                </div>
              </div>
              <div v-else class="text-slate-500">暂无压力数据</div>
            </div>

            <div>
              <div class="mb-2 text-slate-400">关键事件</div>
              <div v-if="publicRoleEvents.length > 0" class="space-y-2">
                <div v-for="(event, index) in publicRoleEvents" :key="`${index}-${event}`"
                     class="rounded-xl bg-slate-900/60 px-3 py-2">
                  <div class="text-slate-200">{{ event }}</div>
                  <div v-if="explainPublicEvent(event)" class="mt-1 text-xs text-slate-400">
                    {{ explainPublicEvent(event) }}
                  </div>
                </div>
              </div>
              <div v-else class="text-slate-500">暂无关键角色事件</div>
            </div>
          </div>
        </div>

        <h3 class="text-lg font-semibold text-white mb-4">行动面板</h3>
        
        <!-- Waiting for action -->
        <div v-if="pendingAction && pendingAction.seat === mySeat" class="space-y-4">
          <div class="text-game-accent-light font-medium">{{ pendingAction.message }}</div>
          
          <!-- Speech input -->
          <div v-if="pendingAction.action_type === 'speech'">
            <textarea v-model="speechInput" 
                      placeholder="输入你的发言..."
                      class="w-full bg-game-dark border border-game-border rounded-lg px-3 py-2 
                             text-white text-sm resize-none h-32 focus:border-game-accent focus:outline-none">
            </textarea>
            <button @click="submitSpeech" 
                    class="w-full mt-2 py-3 bg-game-accent hover:bg-game-accent-light 
                           rounded-lg text-white font-medium transition-colors">
              发送发言
            </button>
          </div>
          
          <!-- Target selection -->
          <div v-else-if="needsTargetSelection">
            <div class="text-sm text-gray-400 mb-2">
              请在左侧圆圈中选择目标玩家
            </div>
            <div v-if="selectedTarget" class="text-white mb-2">
              已选择：{{ selectedTarget }}号
            </div>
            <button @click="submitTargetAction" 
                    :disabled="!selectedTarget"
                    :class="[
                      'w-full py-3 rounded-lg text-white font-medium transition-colors',
                      selectedTarget ? 'bg-game-accent hover:bg-game-accent-light' : 'bg-gray-600 cursor-not-allowed'
                    ]">
              确认选择
            </button>
            <button v-if="canSkip" @click="submitSkip" 
                    class="w-full mt-2 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-white text-sm">
              跳过
            </button>
          </div>

          <div v-else-if="pendingAction.action_type === 'scapegoat'">
            <div class="text-sm text-gray-400 mb-2">
              请选择下一天仍然保有投票权的玩家（可多选）
            </div>
            <div class="space-y-2">
              <button
                v-for="seat in pendingAction.options.candidates || []"
                :key="`scapegoat-${seat}`"
                @click="toggleAllowedVoter(seat)"
                :class="[
                  'w-full rounded-lg border px-3 py-2 text-left transition-colors',
                  selectedAllowedVoters.includes(seat)
                    ? 'border-game-accent bg-game-accent/20 text-white'
                    : 'border-game-border bg-game-dark text-gray-300'
                ]"
              >
                {{ seat }}号
              </button>
            </div>
            <button
              @click="submitScapegoatChoice"
              :disabled="selectedAllowedVoters.length === 0"
              :class="[
                'w-full mt-3 py-3 rounded-lg text-white font-medium transition-colors',
                selectedAllowedVoters.length > 0 ? 'bg-game-accent hover:bg-game-accent-light' : 'bg-gray-600 cursor-not-allowed'
              ]"
            >
              确认名单
            </button>
          </div>
          
          <!-- Witch heal -->
          <div v-else-if="pendingAction.action_type === 'witch_heal'">
            <div class="text-white mb-2">
              今晚 {{ pendingAction.options.victim }}号 被刀
            </div>
            <div class="flex space-x-2">
              <button @click="submitWitchHeal(true)" 
                      class="flex-1 py-3 bg-green-600 hover:bg-green-500 rounded-lg text-white">
                使用解药
              </button>
              <button @click="submitWitchHeal(false)" 
                      class="flex-1 py-3 bg-gray-600 hover:bg-gray-500 rounded-lg text-white">
                不救
              </button>
            </div>
          </div>
          
          <!-- Hunter shoot -->
          <div v-else-if="pendingAction.action_type === 'hunter'">
            <div class="text-sm text-gray-400 mb-2">
              你是猎人，可以开枪带走一人
            </div>
            <div v-if="selectedTarget" class="text-white mb-2">
              已选择：{{ selectedTarget }}号
            </div>
            <button @click="submitTargetAction" 
                    :disabled="!selectedTarget"
                    :class="[
                      'w-full py-3 rounded-lg text-white font-medium transition-colors',
                      selectedTarget ? 'bg-red-600 hover:bg-red-500' : 'bg-gray-600 cursor-not-allowed'
                    ]">
              开枪
            </button>
            <button @click="submitSkip" 
                    class="w-full mt-2 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-white text-sm">
              不开枪
            </button>
          </div>
        </div>
        
        <!-- Waiting for others -->
        <div v-else-if="gameState.waiting_for_human" class="text-center py-8">
          <div class="text-6xl mb-4">⏳</div>
          <p class="text-gray-400">等待 {{ gameState.waiting_for_human }}号 玩家行动...</p>
        </div>
        
        <!-- No action needed -->
        <div v-else class="text-center py-8">
          <div class="text-6xl mb-4">👀</div>
          <p class="text-gray-400">观察局势中...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { gameApi, GameWebSocket, getAvatarUrl } from '@/api'
import { buildDaySummary, buildPendingAction, buildPlayStateSnapshot, parseVoteSnapshot } from '@/gamePlay'
import { explainPublicEvent, extractPublicRoleEvents } from '@/gameReview'
import { buildGodModeDisplayState, fetchAfterlifeActions, fetchGodModeBundle } from '@/gameSpectator'

const route = useRoute()
const router = useRouter()
const gameId = computed(() => route.params.gameId)

// Game state
const gameState = ref({
  phase: 'waiting',
  day_count: 0,
  night_count: 0,
  paused: false,
  winner: null,
  waiting_for_human: null,
  human_action_type: null,
  human_action_options: {},
  current_action_role: null,
  current_action_message: null,
  day_summary: {
    day: 0,
    phase: 'waiting',
    claims: {},
    vote_map: {},
    vote_counts: {},
    pressure_board: [],
  },
})
const players = ref([])
const gameLogs = ref([])
const myRole = ref(null)
const mySeat = ref(null)
const pendingAction = ref(null)
const timer = ref(120)
const wsConnected = ref(false)

// Action state
const selectedTarget = ref(null)
const selectedAllowedVoters = ref([])
const speechInput = ref('')

// 上帝模式
const godModeEnabled = ref(false)  // 本局游戏是否启用了上帝模式
const godModeActive = ref(false)   // 当前是否激活上帝视角
const godModePassword = ref('')    // 用户输入的密码
const showGodModeModal = ref(false)
const godModeLogs = ref([])        // 上帝模式日志（包含私密信息）
const godModePlayers = ref([])     // 上帝模式玩家信息

// 冥界复盘
const showAfterlife = ref(false)
const phantomActions = ref([])

// 投票可视化
const currentVotes = ref({})  // voter -> target
const voteCounts = ref({})    // target -> count
const latestSpeaker = ref(null)  // 当前发言者（用于气泡显示）
const speechBubble = ref({ show: false, seat: null, content: '' })

// WebSocket
let gameWs = null
let timerInterval = null
const logContainer = ref(null)

// Computed
const phaseText = computed(() => {
  const phases = {
    waiting: '等待开始',
    night: '夜晚阶段',
    day: '白天阶段',
    vote: '投票阶段',
    ended: '游戏结束',
  }
  return phases[gameState.value.phase] || gameState.value.phase
})

const needsTargetSelection = computed(() => {
  if (!pendingAction.value) return false
  const type = pendingAction.value.action_type
  return ['guard', 'seer', 'fox', 'wolf', 'vote', 'witch_poison'].includes(type)
})

const canSkip = computed(() => {
  if (!pendingAction.value) return false
  return ['witch_poison'].includes(pendingAction.value.action_type)
})

// 显示的日志（根据上帝模式状态切换）
const displayLogs = computed(() => {
  if (godModeActive.value && godModeLogs.value.length > 0) {
    return godModeLogs.value
  }
  return gameLogs.value
})

const displayDaySummary = computed(() => (
  buildDaySummary(gameState.value.day_summary, gameState.value.day_count, gameState.value.phase)
))

const claimEntries = computed(() => {
  const claims = displayDaySummary.value.claims || {}
  return Object.entries(claims)
    .filter(([, seats]) => Array.isArray(seats) && seats.length > 0)
    .map(([role, seats]) => ({
      role,
      seatsText: seats.map((seat) => `${seat}号`).join('、'),
    }))
})

const voteCountEntries = computed(() => {
  const counts = displayDaySummary.value.vote_counts || {}
  return Object.entries(counts)
    .map(([seat, count]) => ({ seat: Number(seat), count: Number(count) }))
    .sort((a, b) => b.count - a.count || a.seat - b.seat)
})

const pressureBoard = computed(() => displayDaySummary.value.pressure_board || [])
const publicRoleEvents = computed(() => extractPublicRoleEvents(displayLogs.value, { limit: 6 }))
const myPublicRoleEvents = computed(() => {
  if (!mySeat.value) return []
  const seatTag = `${mySeat.value}号`
  return publicRoleEvents.value.filter((event) => event.includes(seatTag))
})

// Methods
const getLogClass = (log) => {
  const classes = {
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
  return classes[log.type] || 'bg-slate-800/30'
}

const getLogTextClass = (log) => {
  const classes = {
    phase: 'text-violet-300 font-medium',
    system: 'text-slate-400',
    death: 'text-red-300',
    end: 'text-amber-300 font-bold',
  }
  return classes[log.type] || 'text-slate-300'
}

const getPlayerPosition = (index, total) => {
  const angle = (index * 2 * Math.PI / total) - Math.PI / 2
  const radius = 250
  const x = 300 + radius * Math.cos(angle)
  const y = 300 + radius * Math.sin(angle)
  return { left: `${x}px`, top: `${y}px` }
}

const getPlayerCenterCoords = (seat) => {
  const index = seat - 1
  const total = players.value.length || 12
  const angle = (index * 2 * Math.PI / total) - Math.PI / 2
  const radius = 250
  return {
    x: 300 + radius * Math.cos(angle),
    y: 300 + radius * Math.sin(angle)
  }
}

const getVoteLineCoords = (voter, target) => {
  const from = getPlayerCenterCoords(parseInt(voter))
  const to = getPlayerCenterCoords(parseInt(target))
  // Shorten line to not overlap with avatars
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.sqrt(dx * dx + dy * dy)
  const ratio = 45 / len  // 45px offset for avatar radius
  return {
    x1: from.x + dx * ratio,
    y1: from.y + dy * ratio,
    x2: to.x - dx * ratio,
    y2: to.y - dy * ratio
  }
}

const parseVotesFromLogs = () => {
  const snapshot = parseVoteSnapshot(gameLogs.value, gameState.value.day_count, displayDaySummary.value)
  currentVotes.value = snapshot.votes
  voteCounts.value = snapshot.counts
}

const showSpeechBubble = (seat, content) => {
  speechBubble.value = { show: true, seat, content: content.substring(0, 30) + '...' }
  latestSpeaker.value = seat
  setTimeout(() => {
    speechBubble.value = { show: false, seat: null, content: '' }
  }, 3000)
}

const getPlayerIcon = (player) => {
  if (!player.alive) return '💀'
  if (player.seat === mySeat.value) return '👤'
  return '🤖'
}

const handleImageError = (e) => {
  e.target.style.display = 'none'
}

const getPlayerBorderClass = (player) => {
  if (!player.alive) return 'border-gray-600'
  if (player.seat === mySeat.value) return 'border-game-accent'
  return 'border-game-border'
}

const getRoleIcon = (role) => {
  const icons = {
    '狼人': '🐺',
    '村民': '👨‍🌾',
    '预言家': '🔮',
    '女巫': '🧙‍♀️',
    '猎人': '🏹',
    '守卫': '🛡️',
    '狐狸': '🦊',
    '天使': '😇',
    '替罪羊': '🐐',
    '丘比特': '💘',
    '白痴': '🤪',
    '长老': '👴',
    '圣徒': '⛪',
    '野孩子': '🧒',
    '共济会': '🤝',
    '被诅咒者': '🕯️',
    '受祝福者': '✨',
  }
  return icons[role] || '❓'
}

const getRoleAnnouncementIcon = (role) => {
  const icons = {
    '守卫': '🛡️',
    '狼人': '🐺',
    '预言家': '🔮',
    '女巫': '🧙‍♀️',
    '猎人': '🏹',
    '狐狸': '🦊',
    '天使': '😇',
    '替罪羊': '🐐',
    '丘比特': '💘',
    '野孩子': '🧒',
  }
  return icons[role] || '🌙'
}

const loadAfterlifeReview = async () => {
  try {
    phantomActions.value = await fetchAfterlifeActions(gameApi, gameId.value)
    showAfterlife.value = true
  } catch (error) {
    console.error('加载冥界复盘失败：', error)
    showAfterlife.value = true
  }
}

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

const selectTarget = (player) => {
  if (!needsTargetSelection.value) return
  if (!player.alive && pendingAction.value?.action_type !== 'hunter') return
  if (player.seat === mySeat.value && pendingAction.value?.action_type !== 'guard') return
  
  // Check if valid candidate
  const candidates = pendingAction.value?.options?.candidates || []
  if (candidates.length > 0 && !candidates.includes(player.seat)) return
  
  selectedTarget.value = player.seat
}

const submitSpeech = () => {
  if (!speechInput.value.trim()) return
  
  gameWs?.sendAction({ content: speechInput.value })
  speechInput.value = ''
}

const submitTargetAction = () => {
  if (!selectedTarget.value) return
  
  gameWs?.sendAction({ target: selectedTarget.value })
  selectedTarget.value = null
}

const toggleAllowedVoter = (seat) => {
  if (!pendingAction.value || pendingAction.value.action_type !== 'scapegoat') return
  const candidates = pendingAction.value.options?.candidates || []
  if (!candidates.includes(seat)) return
  if (selectedAllowedVoters.value.includes(seat)) {
    selectedAllowedVoters.value = selectedAllowedVoters.value.filter((item) => item !== seat)
  } else {
    selectedAllowedVoters.value = [...selectedAllowedVoters.value, seat]
  }
}

const submitScapegoatChoice = () => {
  if (selectedAllowedVoters.value.length === 0) return
  gameWs?.sendAction({ allowed_voters: selectedAllowedVoters.value })
  selectedAllowedVoters.value = []
}

const submitSkip = () => {
  gameWs?.sendAction({ target: null })
  selectedTarget.value = null
}

const submitWitchHeal = (useHeal) => {
  gameWs?.sendAction({ use_heal: useHeal })
}

const togglePause = async () => {
  try {
    if (gameState.value.paused) {
      await gameApi.resume(gameId.value)
    } else {
      await gameApi.pause(gameId.value)
    }
    gameState.value.paused = !gameState.value.paused
  } catch (error) {
    console.error('切换暂停状态失败：', error)
  }
}

const startGame = async () => {
  try {
    await gameApi.start(gameId.value)
  } catch (error) {
    console.error('开始游戏失败：', error)
  }
}

// 上帝模式相关方法
const toggleGodMode = () => {
  if (godModeActive.value) {
    const nextState = buildGodModeDisplayState(false)
    godModeActive.value = nextState.active
    godModeLogs.value = nextState.logs
    godModePlayers.value = nextState.players
    showGodModeModal.value = nextState.showPasswordModal
  } else {
    showGodModeModal.value = true
  }
}

const verifyGodModePassword = async () => {
  try {
    const res = await gameApi.verifyGodMode(gameId.value, godModePassword.value)
    if (res.data.success) {
      const nextState = buildGodModeDisplayState(true)
      godModeActive.value = nextState.active
      showGodModeModal.value = nextState.showPasswordModal
      await loadGodModeData()
    } else {
      alert(res.data.message || '密码错误')
    }
  } catch (error) {
    console.error('验证上帝模式失败：', error)
    alert('验证失败')
  }
}

const loadGodModeData = async () => {
  try {
    const bundle = await fetchGodModeBundle(gameApi, gameId.value, godModePassword.value)
    godModeLogs.value = bundle.logs
    godModePlayers.value = bundle.players
    scrollToBottom()
  } catch (error) {
    console.error('加载上帝模式数据失败：', error)
  }
}

// 定时刷新上帝模式数据
let godModeRefreshInterval = null

const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// WebSocket handlers
const handleWsConnected = (data) => {
  wsConnected.value = true
  mySeat.value = data.seat
  myRole.value = data.role
  
  if (data.game_state) {
    gameState.value = buildPlayStateSnapshot(data.game_state, { paused: false, winner: null })
    players.value = data.game_state.players
    gameLogs.value = data.game_state.logs || []
    
    // 检查上帝模式是否启用
    godModeEnabled.value = data.game_state.god_mode_enabled || false
    
    // Check if action is pending for me
    pendingAction.value = data.game_state.waiting_for_human === mySeat.value
      ? buildPendingAction(mySeat.value, data.game_state.human_action_type, data.game_state.human_action_options)
      : null
  }
  
  scrollToBottom()
}

const handleWsState = (data) => {
  gameState.value = buildPlayStateSnapshot(data)
  players.value = data.players
  
  // Update logs
  if (data.logs) {
    const oldLogsCount = gameLogs.value.length
    gameLogs.value = data.logs
    scrollToBottom()
    
    // Check for new speech logs to show bubble
    if (data.logs.length > oldLogsCount) {
      const newLogs = data.logs.slice(oldLogsCount)
      for (const log of newLogs) {
        if (log.type === 'speech' && log.seat) {
          showSpeechBubble(log.seat, log.content)
          break  // Only show one bubble at a time
        }
      }
    }
    
    // Parse votes if in vote phase
    if (data.phase === 'vote') {
      parseVotesFromLogs()
    } else {
      // Clear votes when not in vote phase
      currentVotes.value = {}
      voteCounts.value = {}
    }
  }
  
  // 如果上帝模式激活，刷新上帝模式数据
  if (godModeActive.value) {
    loadGodModeData()
  }
  
  // Check if action is pending for me
  if (data.waiting_for_human === mySeat.value && data.human_action_type) {
    pendingAction.value = buildPendingAction(mySeat.value, data.human_action_type, data.human_action_options)
    selectedAllowedVoters.value = []
    timer.value = data.human_action_options?.timeout || 120
  } else {
    pendingAction.value = null
    selectedAllowedVoters.value = []
  }
}

const handleWsActionRequired = (data) => {
  if (data.seat === mySeat.value) {
    pendingAction.value = buildPendingAction(data.seat, data.action_type, data.options)
    selectedAllowedVoters.value = []
    timer.value = data.timeout || 120
  }
}

const handleWsRole = (data) => {
  myRole.value = data
}

const handleWsSeerResult = (data) => {
  if (myRole.value) {
    if (!myRole.value.seer_results) {
      myRole.value.seer_results = {}
    }
    myRole.value.seer_results[data.target] = data.result
  }
}

const handleWsFoxResult = (data) => {
  if (myRole.value) {
    if (!myRole.value.fox_checks) {
      myRole.value.fox_checks = {}
    }
    myRole.value.fox_checks[data.target] = data.result
    if (data.result === '没有狼人') {
      myRole.value.fox_power_active = false
    }
  }
}

// 监听上帝模式状态变化
watch(godModeActive, (active) => {
  if (active) {
    // 启动定时刷新
    godModeRefreshInterval = setInterval(() => {
      if (godModeActive.value) {
        loadGodModeData()
      }
    }, 3000)
  } else {
    // 停止定时刷新
    if (godModeRefreshInterval) {
      clearInterval(godModeRefreshInterval)
      godModeRefreshInterval = null
    }
  }
})

// Initialize
onMounted(async () => {
  // Find human seat from URL or API
  try {
    const playersRes = await gameApi.getPlayers(gameId.value)
    players.value = playersRes.data
    
    const humanPlayer = playersRes.data.find(p => p.is_human)
    if (humanPlayer) {
      mySeat.value = humanPlayer.seat
      
      // Get initial role
      const viewRes = await gameApi.getPlayerView(gameId.value, humanPlayer.seat)
      myRole.value = viewRes.data
    }
  } catch (error) {
    console.error('加载初始状态失败：', error)
  }
  
  // Connect WebSocket
  if (mySeat.value) {
    gameWs = new GameWebSocket(gameId.value, mySeat.value, {
      onConnected: handleWsConnected,
      onState: handleWsState,
      onActionRequired: handleWsActionRequired,
      onRole: handleWsRole,
      onSeerResult: handleWsSeerResult,
      onFoxResult: handleWsFoxResult,
      onDisconnect: () => { wsConnected.value = false },
    })
    gameWs.connect()
  }
  
  // Timer
  timerInterval = setInterval(() => {
    if (pendingAction.value && timer.value > 0) {
      timer.value--
    }
  }, 1000)
})

onUnmounted(() => {
  if (gameWs) {
    gameWs.close()
  }
  if (timerInterval) {
    clearInterval(timerInterval)
  }
  if (godModeRefreshInterval) {
    clearInterval(godModeRefreshInterval)
  }
})
</script>

<style scoped>
/* Night overlay breathing animation */
@keyframes night-breathe {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 0.95; }
}

.animate-night-breathe {
  animation: night-breathe 4s ease-in-out infinite;
}

/* Twinkle stars */
@keyframes twinkle {
  0%, 100% { opacity: 0.2; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.5); }
}

.animate-twinkle {
  animation: twinkle 2s ease-in-out infinite;
}

/* Role announcement animation */
@keyframes role-announce {
  0% { opacity: 0; transform: scale(0.8) translateY(20px); }
  20% { opacity: 1; transform: scale(1.1) translateY(0); }
  30% { transform: scale(1) translateY(0); }
  80% { opacity: 1; transform: scale(1) translateY(0); }
  100% { opacity: 0.8; transform: scale(1) translateY(0); }
}

.animate-role-announce {
  animation: role-announce 2s ease-out forwards;
}

/* Night fade transition */
.night-fade-enter-active,
.night-fade-leave-active {
  transition: opacity 1s ease;
}

.night-fade-enter-from,
.night-fade-leave-to {
  opacity: 0;
}

/* Announce fade transition */
.announce-fade-enter-active {
  transition: all 0.5s ease-out;
}

.announce-fade-leave-active {
  transition: all 0.3s ease-in;
}

.announce-fade-enter-from {
  opacity: 0;
  transform: scale(0.9);
}

.announce-fade-leave-to {
  opacity: 0;
  transform: scale(1.1);
}

/* Text shadow for readability */
.text-shadow-lg {
  text-shadow: 0 4px 20px rgba(0, 0, 0, 0.8), 0 2px 10px rgba(0, 0, 0, 0.6);
}

/* Night overlay gradient */
.night-overlay::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 0%, rgba(0, 0, 0, 0.3) 100%);
  pointer-events: none;
}

/* Speech bubble transition */
.bubble-enter-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.bubble-leave-active {
  transition: all 0.2s ease-in;
}

.bubble-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(10px) scale(0.8);
}

.bubble-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px) scale(0.8);
}

/* Vote arrow animation */
@keyframes vote-dash {
  to {
    stroke-dashoffset: -20;
  }
}

.vote-arrow {
  animation: vote-dash 0.5s linear infinite;
}

/* Player speaking indicator */
@keyframes speaking-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(139, 92, 246, 0); }
}

.speaking {
  animation: speaking-pulse 1.5s ease-in-out infinite;
}
</style>
