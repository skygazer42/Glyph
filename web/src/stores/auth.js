import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useAppStore } from '@/stores/app'

async function requestAuth(path, options) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000)
  try {
    const response = await fetch(`/api/auth${path}`, {
      ...options,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'X-Client-Audience': 'staff', ...options.headers },
      signal: controller.signal
    })
    if (!response.ok) {
      let message = path === '/logout' ? '退出登录未完成，请稍后重试。' : '登录服务未完成请求，请稍后重试。'
      if (response.status === 401) {
        message = path === '/login' ? '账号或密码不正确，请重新输入。' : '登录已过期，请重新登录。'
      } else if (response.status === 503) {
        message = '工作人员登录暂不可用，请稍后重试或联系管理员。'
      } else if (response.status === 403) {
        message = '无法验证本次操作，请重新登录后重试。'
      }
      throw Object.assign(new Error(message), { status: response.status })
    }
    return await response.json()
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('登录服务响应超时，请重试。')
    }
    if (error instanceof TypeError) {
      throw new Error('无法连接登录服务，请检查网络后重试。')
    }
    if (error instanceof SyntaxError) {
      throw new Error('登录服务返回的数据无效，请联系管理员。')
    }
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

export const useAuthStore = defineStore('auth', () => {
  const staffUser = ref(null)
  const csrfToken = ref('')
  const expiresAt = ref(null)
  const restoreError = ref('')
  let restoreRequest = null
  let revision = 0
  let lastUsername = ''

  function invalidate() {
    revision += 1
    staffUser.value = null
    csrfToken.value = ''
    expiresAt.value = null
    restoreError.value = ''
  }

  function acceptSession(data) {
    const expiry = typeof data?.expires_at === 'string' &&
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(data.expires_at)
      ? Date.parse(data.expires_at) : NaN
    if (
      typeof data?.user?.username !== 'string' || !data.user.username.trim() ||
      (data.user.full_name !== null && typeof data.user.full_name !== 'string') ||
      !Number.isFinite(expiry) || expiry <= Date.now() ||
      typeof data.csrf_token !== 'string' || !/^[\x21-\x7e]+$/.test(data.csrf_token)
    ) {
      throw new Error('登录服务返回的会话无效，请重新登录或联系管理员。')
    }
    if (lastUsername && lastUsername !== data.user.username) {
      useAppStore().resetPrivateState()
    }
    staffUser.value = { username: data.user.username, full_name: data.user.full_name ?? '' }
    csrfToken.value = data.csrf_token
    expiresAt.value = data.expires_at
    restoreError.value = ''
    lastUsername = data.user.username
    return staffUser.value
  }

  function hasActiveSession() {
    return Boolean(staffUser.value && csrfToken.value && Date.parse(expiresAt.value) > Date.now())
  }

  function staffHeaders() {
    return {
      'X-Client-Audience': 'staff',
      ...(csrfToken.value ? { 'X-CSRF-Token': csrfToken.value } : {})
    }
  }

  async function login(username, password) {
    if (typeof username !== 'string' || !username.trim() || typeof password !== 'string' || !password) {
      throw new Error('请输入工作人员账号和密码。')
    }
    invalidate()
    const requestRevision = revision
    const data = await requestAuth('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.trim(), password })
    })
    if (requestRevision !== revision) {
      throw new Error('登录状态已变化，请重新登录。')
    }
    return acceptSession(data)
  }

  function restore() {
    if (hasActiveSession()) return Promise.resolve(staffUser.value)
    if (restoreRequest) return restoreRequest
    invalidate()
    const requestRevision = revision
    restoreRequest = (async () => {
      try {
        const data = await requestAuth('/session', { method: 'GET' })
        if (requestRevision !== revision) return null
        return acceptSession(data)
      } catch (error) {
        if (requestRevision !== revision) return null
        invalidate()
        if (error.status === 401) return null
        restoreError.value = error.message
        throw error
      } finally {
        restoreRequest = null
      }
    })()
    return restoreRequest
  }

  async function logout() {
    revision += 1
    const requestRevision = revision
    const data = await requestAuth('/logout', { method: 'POST', headers: staffHeaders() })
    if (data?.success !== true) {
      throw new Error('登录服务未确认退出，请重试。')
    }
    if (requestRevision !== revision) {
      throw new Error('登录状态已变化，请确认当前账号后重试。')
    }
    invalidate()
  }

  return { staffUser, csrfToken, expiresAt, restoreError, login, restore, logout, invalidate, hasActiveSession, staffHeaders }
})
