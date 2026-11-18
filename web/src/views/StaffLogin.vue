<template>
  <div class="staff-login">
    <header class="staff-login-header">
      <div class="staff-login-header-inner">
      <router-link to="/agent" class="staff-login-brand" aria-label="政策知识服务平台公众咨询">
        <PlatformMark width="32" height="32" />
        <span>政策知识服务平台</span>
      </router-link>
      <div class="staff-login-header-actions">
        <el-tooltip :content="isDark ? '切换浅色界面' : '切换深色界面'" placement="bottom">
          <button type="button" class="staff-login-theme" :aria-label="isDark ? '切换浅色界面' : '切换深色界面'" @click="toggleTheme">
            <el-icon><component :is="isDark ? Sunny : Moon" /></el-icon>
          </button>
        </el-tooltip>
        <router-link to="/agent" class="staff-login-public">公众咨询 <el-icon aria-hidden="true"><TopRight /></el-icon></router-link>
      </div>
      </div>
    </header>
    <main class="staff-login-main">
      <section class="staff-login-panel" aria-labelledby="staff-login-title">
        <p class="staff-login-caption">工作人员入口</p>
        <h1 id="staff-login-title">登录工作台</h1>
        <p class="staff-login-description">使用工作人员账号，进入政策资料与规则工作区。</p>
        <p v-if="notice" class="staff-login-notice" role="status">{{ notice }}</p>
        <p v-if="errorMessage" id="staff-login-error" class="staff-login-error" role="alert"><el-icon aria-hidden="true"><WarningFilled /></el-icon><span>{{ errorMessage }}</span></p>
        <el-form ref="formElement" :model="form" :rules="rules" label-position="top" hide-required-asterisk :disabled="busy" :aria-busy="busy" :aria-describedby="errorMessage ? 'staff-login-error' : undefined" @submit.prevent="submitLogin">
          <el-form-item label="账号" prop="username" label-for="staff-username">
            <el-input id="staff-username" ref="usernameInput" v-model="form.username" name="username" autocomplete="username" :prefix-icon="User" placeholder="输入工作人员账号" />
          </el-form-item>
          <el-form-item label="密码" prop="password" label-for="staff-password">
            <el-input id="staff-password" ref="passwordInput" v-model="form.password" name="password" type="password" autocomplete="current-password" :prefix-icon="Lock" placeholder="输入密码" show-password />
          </el-form-item>
          <el-button class="staff-login-submit" type="primary" native-type="submit" :loading="busy" :disabled="busy">{{ restoring ? '正在确认登录状态' : submitting ? '正在登录' : '登录工作台' }}</el-button>
        </el-form>
        <p class="staff-login-account-note">账号由平台管理员分配。</p>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, Moon, Sunny, TopRight, User, WarningFilled } from '@element-plus/icons-vue'
import PlatformMark from '@/components/workbench/PlatformMark.vue'
import { useTheme } from '@/composables/useTheme'
import { useAuthStore } from '@/stores/auth'
import { getStaffDestination } from '@/utils/staffNavigation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isDark, toggleTheme } = useTheme()
const form = reactive({ username: '', password: '' })
const formElement = ref(null)
const usernameInput = ref(null)
const passwordInput = ref(null)
const restoring = ref(true)
const submitting = ref(false)
const errorMessage = ref('')
const busy = computed(() => restoring.value || submitting.value)
const destination = computed(() => getStaffDestination(route.query.redirect))
const notice = computed(() => {
  if (route.query.reason === 'expired') return '登录已过期，请重新登录以继续操作。'
  if (route.query.reason === 'cache-clear-failed') return '已退出登录，但浏览器中的会话记录未能清理。请关闭当前窗口并联系管理员。'
  return ''
})
const rules = {
  username: [{ type: 'string', required: true, whitespace: true, message: '请输入工作人员账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}
let disposed = false

async function submitLogin() {
  if (busy.value) return
  submitting.value = true
  const valid = await formElement.value.validate().catch(() => false)
  if (!valid) {
    submitting.value = false
    return
  }
  errorMessage.value = ''
  try {
    await authStore.login(form.username.trim(), form.password)
  } catch (error) {
    form.password = ''
    submitting.value = false
    if (!disposed) {
      errorMessage.value = error.message
      await nextTick()
      passwordInput.value?.focus()
    }
    return
  }
  form.password = ''
  if (!disposed) await router.replace(destination.value)
  submitting.value = false
}

onMounted(async () => {
  try {
    await authStore.restore()
    if (!disposed && authStore.hasActiveSession()) await router.replace(destination.value)
  } catch (error) {
    if (!disposed) errorMessage.value = authStore.restoreError || error.message
  } finally {
    restoring.value = false
    if (!disposed && !authStore.hasActiveSession()) {
      await nextTick()
      usernameInput.value?.focus()
    }
  }
})

onBeforeUnmount(() => {
  disposed = true
  form.password = ''
})
</script>

<style scoped>
.staff-login {
  --el-color-primary: var(--wb-blue);
  --el-color-primary-dark-2: var(--wb-blue-hover);
  --el-color-primary-light-9: var(--wb-blue-soft);
  --el-color-danger: var(--wb-error);
  --el-text-color-primary: var(--wb-ink);
  --el-text-color-regular: var(--wb-ink);
  --el-text-color-placeholder: var(--wb-muted);
  --el-border-color: var(--wb-border);
  --el-fill-color-blank: var(--wb-surface);
  --el-fill-color-light: var(--wb-tint);
  --el-bg-color: var(--wb-surface);
  --el-disabled-bg-color: var(--wb-tint);
  --el-disabled-text-color: var(--wb-muted);
  --el-border-radius-base: var(--wb-radius);
  min-height: 100dvh;
  display: grid;
  grid-template-rows: auto 1fr;
  color: var(--wb-ink);
  background-color: var(--wb-canvas);
  background-image: radial-gradient(circle, color-mix(in srgb, var(--wb-border) 65%, transparent) .7px, transparent .8px);
  background-size: 24px 24px;
  font: var(--wb-text-size)/1.6 var(--wb-font);
  font-variant-numeric: tabular-nums;
}
.staff-login-header { padding: 0 32px; border-bottom: 1px solid var(--wb-line); background: var(--wb-surface); }
.staff-login-header-inner { display: flex; align-items: center; justify-content: space-between; gap: 20px; max-width: 1280px; min-height: var(--wb-public-header-height); margin-inline: auto; }
.staff-login-brand { display: inline-flex; align-items: center; gap: 10px; color: var(--wb-ink); font-size: 17px; font-weight: 600; text-decoration: none; }
.staff-login-brand svg { flex-shrink: 0; }
.staff-login-header-actions { display: flex; align-items: center; gap: 20px; }
.staff-login-theme { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; padding: 0; border: 0; border-radius: var(--wb-radius); color: var(--wb-muted); background: transparent; font-size: 17px; cursor: pointer; }
.staff-login-theme:hover { background: var(--wb-tint); }
.staff-login-public { display: inline-flex; align-items: center; gap: 5px; color: var(--wb-muted); font-size: 14px; text-decoration: none; white-space: nowrap; }
.staff-login-public:hover { color: var(--wb-blue); }
.staff-login-main { display: grid; align-content: start; padding: clamp(48px, 14vh, 144px) 20px 40px; }
.staff-login-panel { width: min(100%, 420px); margin: 0 auto; padding: 36px 32px; border: 1px solid var(--wb-line); border-radius: 12px; background: var(--wb-surface); box-shadow: 0 12px 36px color-mix(in srgb, var(--wb-ink) 4%, transparent), 0 2px 6px color-mix(in srgb, var(--wb-ink) 2%, transparent); }
.staff-login-caption { margin: 0 0 8px; color: var(--wb-muted); font-size: 13px; }
.staff-login-panel h1 { margin: 0; font-size: var(--wb-title-size); font-weight: 600; line-height: 1.5; }
.staff-login-description { margin: 10px 0 28px; color: var(--wb-muted); font-size: 14px; }
.staff-login-notice { margin: 0 0 20px; padding: 12px; border-radius: var(--wb-radius); color: var(--wb-ink); background: var(--wb-blue-soft); font-size: 14px; }
.staff-login-error { display: flex; align-items: flex-start; gap: 8px; margin: 0 0 20px; padding: 12px 14px; border: 1px solid var(--wb-error-border); border-radius: 8px; color: var(--wb-error); background: var(--wb-error-soft); font-size: 14px; overflow-wrap: anywhere; }
.staff-login-error .el-icon { flex-shrink: 0; margin-top: 4px; }
.staff-login-panel :deep(.el-form-item) { margin-bottom: 22px; }
.staff-login-panel :deep(.el-form-item__label) { height: auto; margin-bottom: 8px; color: var(--wb-ink); font-size: var(--wb-text-size); line-height: 24px; }
.staff-login-panel :deep(.el-input__wrapper) { min-height: 40px; background: var(--wb-surface); box-shadow: 0 0 0 1px var(--wb-border) inset; font-size: var(--wb-text-size); }
.staff-login-panel :deep(.el-input__inner) { color: var(--wb-ink); font: inherit; }
.staff-login-panel :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 2px var(--wb-blue) inset; }
.staff-login-panel :deep(.el-form-item.is-error .el-input__wrapper) { box-shadow: 0 0 0 1px var(--wb-error) inset; }
.staff-login-panel :deep(.el-form-item__error) { color: var(--wb-error); font-size: 12px; }
.staff-login-submit { --el-button-text-color: var(--wb-surface); --el-button-hover-text-color: var(--wb-surface); --el-button-active-text-color: var(--wb-surface); --el-button-hover-bg-color: var(--wb-blue-hover); --el-button-hover-border-color: var(--wb-blue-hover); --el-button-disabled-text-color: var(--wb-muted); --el-button-disabled-bg-color: var(--wb-tint); --el-button-disabled-border-color: var(--wb-line); width: 100%; min-height: 40px; margin-top: 2px; font: inherit; }
.staff-login .staff-login-submit.el-button { border: 1px solid var(--wb-blue); color: var(--wb-surface); background: var(--wb-blue); box-shadow: none; transform: none; letter-spacing: normal; }
.staff-login .staff-login-submit.el-button:not(:disabled):hover,
.staff-login .staff-login-submit.el-button:not(:disabled):focus { border-color: var(--wb-blue-hover); color: var(--wb-surface); background: var(--wb-blue-hover); box-shadow: none; transform: none; }
.staff-login .staff-login-submit.el-button:disabled { border-color: var(--wb-line); color: var(--wb-muted); background: var(--wb-tint); box-shadow: none; }
.staff-login-account-note { margin: 20px 0 0; color: var(--wb-muted); font-size: 13px; text-align: center; }
.staff-login a:focus-visible, .staff-login button:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 3px; }
@media (max-width: 600px) {
  .staff-login-header { padding: 0 16px; }
  .staff-login-header-inner { gap: 10px; min-height: 64px; }
  .staff-login-brand { gap: 7px; font-size: 14px; }
  .staff-login-brand svg { width: 28px; height: 28px; }
  .staff-login-header-actions { gap: 8px; }
  .staff-login-public { min-height: 44px; font-size: 12px; }
  .staff-login-theme { width: 44px; height: 44px; }
  .staff-login-main { padding: 36px 16px; }
  .staff-login-panel { padding: 26px 22px; }
  .staff-login-panel :deep(.el-input__wrapper), .staff-login-submit { min-height: 44px; }
  .staff-login-panel :deep(.el-input__inner) { font-size: 16px; }
}
</style>
