import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomePage.vue')
  },
  {
    path: '/agent',
    name: 'Agent',
    component: () => import('@/views/AgentChat.vue')
  },
  {
    path: '/dsl',
    name: 'DSL',
    component: () => import('@/views/DSLGenerator.vue')
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgeBase.vue')
  },
  {
    path: '/graph',
    name: 'Graph',
    component: () => import('@/views/KnowledgeGraph.vue')
  },
  // 兼容旧链接
  {
    path: '/knowledge-graph',
    redirect: '/graph'
  },
  {
    path: '/dsl-generator',
    redirect: '/dsl'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
