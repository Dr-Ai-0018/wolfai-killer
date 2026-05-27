<template>
  <div class="min-h-screen stars-bg">
    <nav class="fixed top-0 left-0 right-0 z-50 glass">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <router-link to="/" class="flex items-center space-x-3">
            <img src="/wolf.svg" alt="狼人杀徽记" class="w-8 h-8" />
            <span class="text-xl font-bold text-game-accent-light">月夜狼人杀</span>
          </router-link>
          
          <div class="flex items-center space-x-6">
            <router-link 
              to="/" 
              class="text-gray-300 hover:text-white transition-colors"
              :class="{ 'text-game-accent-light': $route.path === '/' }"
            >
              首页
            </router-link>
            <router-link 
              to="/setup" 
              class="text-gray-300 hover:text-white transition-colors"
              :class="{ 'text-game-accent-light': $route.path === '/setup' }"
            >
              开始游戏
            </router-link>
            <router-link 
              to="/history" 
              class="text-gray-300 hover:text-white transition-colors"
              :class="{ 'text-game-accent-light': $route.path === '/history' }"
            >
              历史记录
            </router-link>
          </div>
        </div>
      </div>
    </nav>
    
    <main class="pt-16">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>
