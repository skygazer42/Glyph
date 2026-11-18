import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getStaffDestination } from '@/utils/staffNavigation'

const routes = [
  {
    path: '/',
    name: 'Home',
    redirect: '/agent'
  },
  {
    path: '/agent',
    name: 'Agent',
    component: () => import('@/views/AgentChat.vue'),
    props: { workspace: false },
    meta: { title: '政策咨询' }
  },
  {
    path: '/login',
    name: 'StaffLogin',
    component: () => import('@/views/StaffLogin.vue'),
    meta: { workspace: false, title: '工作人员登录' }
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('@/views/AgentChat.vue'),
    props: { workspace: true },
    meta: { workspace: true, title: '智能问答' }
  },
  {
    path: '/dsl',
    name: 'DSL',
    component: () => import('@/views/DSLGenerator.vue'),
    meta: { workspace: true, title: '规则管理' }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgeBase.vue'),
    meta: { workspace: true, title: '知识库' }
  },
  {
    path: '/graph',
    name: 'Graph',
    component: () => import('@/views/KnowledgeGraph.vue'),
    meta: { workspace: true, title: '知识图谱' }
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

router.beforeEach(to => {
  if (!to.meta.workspace) return true
  const authStore = useAuthStore()
  if (authStore.hasActiveSession()) return true
  const expired = Boolean(authStore.staffUser)
  authStore.invalidate()
  return {
    path: '/login',
    query: { redirect: getStaffDestination(to.fullPath), ...(expired ? { reason: 'expired' } : {}) },
    replace: true
  }
})

router.afterEach(to => {
  document.title = to.meta.title ? `${to.meta.title} · 政策知识服务平台` : '政策知识服务平台'
})

export default router
