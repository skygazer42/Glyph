import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dsl'
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
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
