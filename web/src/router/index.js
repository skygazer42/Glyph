import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Dashboard.vue')
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/ChatConsultation.vue')
  },
  {
    path: '/calculator',
    name: 'Calculator',
    component: () => import('@/views/PolicyCalculator.vue')
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgeBase.vue')
  },
  // 保留旧路由以保持兼容
  {
    path: '/agent',
    redirect: '/chat'
  },
  {
    path: '/dsl',
    redirect: '/calculator'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
