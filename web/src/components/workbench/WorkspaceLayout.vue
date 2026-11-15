<template>
  <div class="policy-workbench module-workbench evidence-collapsed" :class="{ 'navigation-collapsed': navigationCollapsed }">
    <WorkbenchSidebar
      v-if="!isMobile"
      :collapsed="navigationCollapsed"
      :sessions="[]"
      :show-recent="false"
      action-label="进入智能问答"
      @create="router.push('/agent')"
    >
      <template #profile-action>
        <el-tooltip :content="isDark ? '切换为浅色' : '切换为深色'" placement="right">
          <button type="button" class="workbench-icon" :aria-label="isDark ? '切换为浅色' : '切换为深色'" @click="toggleTheme">
            <el-icon><component :is="isDark ? Sunny : Moon" /></el-icon>
          </button>
        </el-tooltip>
      </template>
    </WorkbenchSidebar>
    <header class="workbench-header">
      <el-tooltip :content="isMobile ? '打开功能导航' : navigationCollapsed ? '展开功能导航' : '收起功能导航'" placement="bottom">
        <button
          type="button"
          class="workbench-icon"
          :aria-label="isMobile ? '打开功能导航' : navigationCollapsed ? '展开功能导航' : '收起功能导航'"
          :aria-expanded="isMobile ? mobileNavigationVisible : !navigationCollapsed"
          @click="toggleNavigation"
        >
          <el-icon><component :is="navigationCollapsed || isMobile ? Expand : Fold" /></el-icon>
        </button>
      </el-tooltip>
      <div class="consultation-heading">
        <h1>{{ currentModule.title }}</h1>
        <span>{{ currentModule.context }}</span>
      </div>
      <div class="workbench-header-actions">
        <el-tooltip content="使用说明" placement="bottom">
          <button type="button" class="workbench-icon" aria-label="使用说明" @click="helpVisible = true">
            <el-icon><QuestionFilled /></el-icon>
          </button>
        </el-tooltip>
        <router-link class="module-consult-link" to="/agent">
          <el-icon><ChatDotSquare /></el-icon><span>智能问答</span>
        </router-link>
      </div>
    </header>
    <main id="module-content" class="module-content" :class="{ 'is-graph': route.path === '/graph', 'is-knowledge': route.path === '/knowledge' }">
      <slot />
    </main>
    <el-drawer v-model="mobileNavigationVisible" direction="ltr" size="260px" :with-header="false" class="glyph-dialog module-navigation-drawer" aria-label="功能导航">
      <WorkbenchSidebar :sessions="[]" :show-recent="false" action-label="进入智能问答" @create="router.push('/agent')">
        <template #profile-action>
          <el-tooltip :content="isDark ? '切换为浅色' : '切换为深色'" placement="top">
            <button type="button" class="workbench-icon" :aria-label="isDark ? '切换为浅色' : '切换为深色'" @click="toggleTheme"><el-icon><component :is="isDark ? Sunny : Moon" /></el-icon></button>
          </el-tooltip>
          <button type="button" class="workbench-icon" aria-label="关闭功能导航" @click="mobileNavigationVisible = false"><el-icon><Close /></el-icon></button>
        </template>
      </WorkbenchSidebar>
    </el-drawer>
    <el-dialog v-model="helpVisible" :title="currentModule.title + '使用说明'" width="480px" class="glyph-dialog">
      <p class="module-help">{{ currentModule.help }}</p>
      <template #footer><el-button type="primary" @click="helpVisible = false">知道了</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotSquare, Close, Expand, Fold, Moon, QuestionFilled, Sunny } from '@element-plus/icons-vue'
import WorkbenchSidebar from './WorkbenchSidebar.vue'
import { useTheme } from '@/composables/useTheme'
import '@/styles/workbench.css'
import '@/styles/modules.css'

const route = useRoute()
const router = useRouter()
const { isDark, toggleTheme } = useTheme()
const mobileQuery = window.matchMedia('(max-width: 699px)')
const isMobile = ref(mobileQuery.matches)
const navigationCollapsed = ref(window.innerWidth < 1100)
const mobileNavigationVisible = ref(false)
const helpVisible = ref(false)
const modules = {
  '/knowledge': { title: '政策知识库', context: '资料处理与知识检索', help: '导入资料后，在文档工作区核对原文与解析正文，调整切块边界并保存处理方案。入库由你手动确认；完成后可在知识检索中查找内容并返回来源文档。' },
  '/dsl': { title: 'DSL 规则', context: '政策规则工作区', help: '粘贴政策文本后生成规则，核对输出内容，再保存或使用输入参数测试。下方规则库保留已保存的规则及其状态。' },
  '/graph': { title: '知识图谱', context: '政策实体与关联', help: '搜索政策实体，并调整关联层级聚焦局部关系。可拖动画布、缩放查看；清除筛选回到完整图谱。' }
}
const currentModule = computed(() => modules[route.path] || modules['/knowledge'])
const updateMobileLayout = (event) => {
  isMobile.value = event.matches
  mobileNavigationVisible.value = false
}
const toggleNavigation = () => {
  if (isMobile.value) mobileNavigationVisible.value = !mobileNavigationVisible.value
  else navigationCollapsed.value = !navigationCollapsed.value
}
mobileQuery.addEventListener('change', updateMobileLayout)
onBeforeUnmount(() => mobileQuery.removeEventListener('change', updateMobileLayout))
watch(() => route.path, () => { mobileNavigationVisible.value = false; helpVisible.value = false })
</script>
