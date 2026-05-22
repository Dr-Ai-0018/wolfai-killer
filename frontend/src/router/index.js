import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/setup',
    name: 'GameSetup',
    component: () => import('@/views/GameSetup.vue')
  },
  {
    path: '/game/:gameId',
    name: 'GamePlay',
    component: () => import('@/views/GamePlay.vue'),
    props: true
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/History.vue')
  },
  {
    path: '/history/:gameId',
    name: 'GameDetail',
    component: () => import('@/views/GameDetail.vue'),
    props: true
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/Admin.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
