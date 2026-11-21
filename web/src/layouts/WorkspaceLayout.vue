<template>
  <div class="module-workbench" :class="{ 'is-navigation-collapsed': navigationCollapsed }">
    <aside id="workspace-sidebar" class="workspace-sidebar">
      <router-link to="/knowledge" class="workspace-brand" aria-label="政策知识服务平台工作台">
        <PlatformMark class="workspace-platform-symbol" width="32" height="32" />
        <span class="workspace-brand-name">政策知识服务平台</span>
      </router-link>
      <p class="workspace-nav-caption">工作区</p>
      <nav class="workspace-topnav" aria-label="后台功能导航">
        <router-link v-for="item in navigation" :key="item.path" :to="item.path"
          :class="{ 'is-current': route.path === item.path }"
          :title="item.label"
          :aria-current="route.path === item.path ? 'page' : undefined">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
          <span v-if="item.path === '/knowledge' && appStore.documentCount" class="workspace-nav-count">{{ appStore.documentCount }}</span>
        </router-link>
      </nav>
      <div class="workspace-sidebar-bottom">
        <router-link to="/agent" class="workspace-public-link" title="公众咨询"><el-icon><ChatDotRound /></el-icon><span>公众咨询</span><el-icon><TopRight /></el-icon></router-link>
      </div>
    </aside>
    <header class="workspace-header">
      <div class="workspace-breadcrumb" aria-label="当前位置">
        <button type="button" class="workspace-icon workspace-nav-toggle" :aria-label="navigationCollapsed ? '展开导航' : '收起导航'" :aria-expanded="!navigationCollapsed" aria-controls="workspace-sidebar" @click="navigationCollapsed = !navigationCollapsed"><el-icon><component :is="navigationCollapsed ? Expand : Fold" /></el-icon></button>
        <span class="workspace-mobile-title"><PlatformMark class="workspace-platform-symbol" width="26" height="26" />政策知识服务平台</span>
        <span v-if="route.path === '/knowledge' && !route.query.doc">知识库</span>
        <template v-else>
          <router-link :to="breadcrumb.parentPath">{{ breadcrumb.parent }}</router-link>
          <el-icon aria-hidden="true"><Right /></el-icon>
          <span>{{ breadcrumb.current }}</span>
        </template>
      </div>
      <div v-if="route.path === '/workbench'" id="workspace-consultation-actions" class="workspace-consultation-actions" />
      <div class="workspace-header-tools">
        <template v-if="route.path !== '/workbench'">
          <el-tooltip :content="isDark ? '切换浅色界面' : '切换深色界面'" placement="bottom">
            <button type="button" class="workspace-icon" :aria-label="isDark ? '切换浅色界面' : '切换深色界面'" @click="toggleTheme"><el-icon><component :is="isDark ? Sunny : Moon" /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="使用说明" placement="bottom">
            <button type="button" class="workspace-help-link" :class="{ 'is-compact': route.path === '/knowledge' }" aria-label="当前模块使用说明" @click="helpVisible = true"><el-icon><QuestionFilled /></el-icon><span v-if="route.path !== '/knowledge'">使用说明</span></button>
          </el-tooltip>
        </template>
        <router-link to="/agent" class="workspace-mobile-public">公众咨询 <el-icon><TopRight /></el-icon></router-link>
        <el-dropdown v-if="route.path === '/workbench'" ref="accountDropdown" class="workspace-account-dropdown" trigger="click" placement="bottom-end" popper-class="workspace-account-menu" @command="handleAccountAction">
          <button ref="accountTrigger" type="button" class="workspace-account-trigger" :disabled="loggingOut" :aria-label="'账号与界面设置：' + staffDisplayName" @keydown.esc.stop="closeAccountMenu"><el-icon><User /></el-icon><span :title="staffDisplayName">{{ staffDisplayName }}</span><el-icon class="workspace-account-arrow"><ArrowDown /></el-icon></button>
          <template #dropdown>
            <el-dropdown-menu @keydown.esc.capture.stop="closeAccountMenu">
              <el-dropdown-item command="theme" :icon="isDark ? Sunny : Moon">{{ isDark ? '切换浅色界面' : '切换深色界面' }}</el-dropdown-item>
              <el-dropdown-item command="help" :icon="QuestionFilled">使用说明</el-dropdown-item>
              <el-dropdown-item command="logout" :icon="SwitchButton" :disabled="loggingOut" divided>{{ loggingOut ? '正在退出…' : '退出登录' }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <div v-else class="workspace-account">
          <span class="workspace-account-name" :title="staffDisplayName">{{ staffDisplayName }}</span>
          <el-button class="workspace-logout" link :loading="loggingOut" :disabled="loggingOut" aria-label="退出登录" @click="logout">
            <el-icon v-if="!loggingOut" aria-hidden="true"><SwitchButton /></el-icon><span>退出</span>
          </el-button>
        </div>
      </div>
    </header>
    <main id="module-content" ref="contentElement" class="module-content" :class="{ 'is-graph': route.path === '/graph', 'is-chat': route.path === '/workbench', 'is-knowledge': route.path === '/knowledge' }">
      <el-alert v-if="logoutError" class="workspace-logout-error" type="error" :title="logoutError" show-icon @close="logoutError = ''" />
      <slot />
    </main>
    <el-dialog v-model="helpVisible" :title="route.meta.title + '使用说明'" width="480px" class="glyph-dialog">
      <p class="module-help">{{ helpText }}</p>
      <template #footer><el-button type="primary" @click="helpVisible = false">知道了</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, ChatDotRound, Connection, DocumentChecked, Expand, Fold, FolderOpened, Moon, QuestionFilled, Right, Sunny, SwitchButton, TopRight, User } from '@element-plus/icons-vue'
import PlatformMark from '@/components/brand/PlatformMark.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { clearStaffConversationCache } from '@/composables/useLocalStorage'
import '@/styles/workspace-layout.css'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()
const { isDark, toggleTheme } = useTheme()
const helpVisible = ref(false)
const accountTrigger = ref(null)
const accountDropdown = ref(null)
const navigationCollapsed = ref(false)
const loggingOut = ref(false)
const logoutError = ref('')
const staffDisplayName = computed(() => authStore.staffUser?.full_name.trim() || authStore.staffUser?.username || '')
const contentElement = ref(null)
const documents = computed(() => appStore.kbState.documents)
const navigation = [
  { path: '/workbench', label: '智能问答', icon: ChatDotRound },
  { path: '/knowledge', label: '知识库', icon: FolderOpened },
  { path: '/graph', label: '知识图谱', icon: Connection },
  { path: '/dsl', label: '规则管理', icon: DocumentChecked }
]
const breadcrumbs = {
  '/workbench': { parent: '问答', parentPath: '/workbench', current: '政策咨询' },
  '/knowledge': { parent: '知识库', parentPath: '/knowledge', current: '政策资料' },
  '/graph': { parent: '知识库', parentPath: '/knowledge', current: '知识图谱' },
  '/dsl': { parent: '规则', parentPath: '/dsl', current: '规则管理' }
}
const breadcrumb = computed(() => route.path === '/knowledge' && route.query.doc
  ? { parent: '知识库', parentPath: route.query.tab === 'search' ? '/knowledge?tab=search' : '/knowledge', current: '文档工作区' }
  : breadcrumbs[route.path])
const helpByPath = {
  '/workbench': '描述政策问题后提交咨询，可上传附件或填写测算条件。后台问答支持选择数据库连接；公众咨询入口使用独立页面。答复中的引用编号可打开对应政策依据。',
  '/knowledge': '先导入政策资料，再打开文档核对原文与解析正文。切块预览与处理配置可单独调整和保存；解析与入库需要明确执行，不会因查看文档自动开始。',
  '/graph': '搜索政策实体并调整关联层级，可聚焦局部关系。点击实体查看说明、相邻关系和来源标识；复位恢复当前视图，查看全图返回完整图谱。',
  '/dsl': '粘贴政策文本生成规则，核对规则后保存并使用输入参数测试。测试结果使用接口返回值；历史政策需核对适用范围。'
}
const helpText = computed(() => helpByPath[route.path])

function closeAccountMenu() {
  accountDropdown.value?.handleClose()
  accountTrigger.value?.focus()
}

function handleAccountAction(command) {
  accountTrigger.value?.focus()
  if (command === 'theme') toggleTheme()
  else if (command === 'help') helpVisible.value = true
  else if (command === 'logout') logout()
}

async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  const username = authStore.staffUser.username
  let reason
  try {
    await authStore.logout()
  } catch (error) {
    if (error.status !== 401) {
      logoutError.value = error.message
      loggingOut.value = false
      return
    }
    authStore.invalidate()
    reason = 'expired'
  }
  try {
    appStore.resetPrivateState()
    await clearStaffConversationCache(username)
  } catch (error) {
    console.error('已退出登录，但本地会话清理失败:', error)
    reason = 'cache-clear-failed'
  }
  await router.replace({ path: '/login', query: reason ? { reason } : {} })
  loggingOut.value = false
}

watch(() => route.path, () => {
  helpVisible.value = false
  contentElement.value.scrollTop = 0
}, { flush: 'post' })
</script>

<style scoped>
.workspace-consultation-actions { margin-left: auto; }
.workspace-account-trigger { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 8px; border: 0; border-radius: var(--wb-radius); background: transparent; color: var(--wb-muted); font: 13px var(--wb-font); cursor: pointer; }
.workspace-account-trigger:hover { background: var(--wb-tint); color: var(--wb-ink); }
.workspace-account-trigger > span { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.workspace-account-arrow { font-size: 11px; }
.workspace-help-link.is-compact { width: 32px; height: 32px; border-radius: var(--wb-radius); font-size: 14px; }
.workspace-help-link.is-compact:hover { background: var(--wb-tint); }
.workspace-account { display: flex; align-items: center; gap: 12px; min-width: 0; padding-left: 14px; border-left: 1px solid var(--wb-line); }
.workspace-account-name { display: block; max-width: 140px; overflow: hidden; color: var(--wb-ink); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.workspace-logout { gap: 5px; min-height: 36px; padding: 0 2px; color: var(--wb-muted); font: 13px var(--wb-font); }
.workspace-logout:not(:disabled):hover { color: var(--wb-blue); }
.workspace-logout-error { flex-shrink: 0; margin-bottom: 16px; color: var(--wb-error); background: var(--wb-tint); }
@media (max-width: 1099px) {
  .workspace-consultation-actions { display: none; }
}
@media (max-width: 760px) {
  .module-workbench { grid-template-rows: auto minmax(0, 1fr) auto; }
  .workspace-header { flex-wrap: wrap; padding-top: 12px; padding-bottom: 10px; }
  .workspace-header-tools { width: 100%; gap: 12px; }
  .workspace-account-dropdown { margin-left: auto; }
  .workspace-account-trigger { min-height: 44px; }
  .workspace-account { gap: 10px; margin-left: auto; padding-left: 12px; }
  .workspace-account-name { max-width: clamp(64px, 24vw, 120px); }
  .workspace-logout { min-height: 44px; }
}
</style>
