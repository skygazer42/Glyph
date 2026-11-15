<template>
<aside id="workbench-navigation" class="workbench-sidebar" :class="{ 'is-collapsed': collapsed }" aria-label="工作台导航">
  <router-link to="/agent" class="workbench-brand" aria-label="Glyph 工作台">
    <GlyphMark />
    <div class="brand-copy">
      <strong>
        Glyph
      </strong>
      <span>
        政策智能服务
      </span>
    </div>
  </router-link>
  <el-tooltip :content="actionLabel" placement="right" :disabled="!collapsed">
    <button type="button" class="new-consultation" :aria-label="actionLabel" @click="$emit('create')">
      <el-icon>
        <Plus />
      </el-icon>
      <span class="nav-label">
        {{ actionLabel }}
      </span>
    </button>
  </el-tooltip>
  <nav class="workspace-navigation" aria-label="功能导航">
    <p class="navigation-label">
      工作台
    </p>
    <el-tooltip v-for="item in navigation" :key="item.path" :content="item.label" placement="right" :disabled="!collapsed">
      <router-link
        :to="item.path"
        class="workspace-link"
        :aria-label="item.label"
        :class="{ 'is-current': item.path === route.path }"
        :aria-current="item.path === route.path ? 'page' : undefined"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <span class="nav-label">
          {{ item.label }}
        </span>
        <span v-if="item.path === route.path" class="current-dot" />
      </router-link>
    </el-tooltip>
  </nav>
  <section v-if="showRecent && !collapsed" class="recent-consultations" aria-label="最近咨询">
    <div class="recent-heading">
      <span>
        最近咨询
      </span>
      <el-tooltip content="管理全部会话" placement="right">
        <button type="button" class="workbench-icon" aria-label="管理全部会话" @click="$emit('manage')">
          <el-icon>
            <Clock />
          </el-icon>
        </button>
      </el-tooltip>
    </div>
    <button
      v-for="session in recentSessions"
      :key="session.id"
      type="button"
      class="recent-session"
      :class="{ 'is-current': session.id === currentSessionId }"
      :aria-current="session.id === currentSessionId ? 'true' : undefined"
      :title="session.title"
      @click="$emit('select', session.id)"
    >
      <span class="session-title">
        {{ session.title }}
      </span>
      <span class="session-preview">
        {{ session.lastMessage || '等待开始咨询' }}
      </span>
    </button>
    <p v-if="!recentSessions.length" class="sidebar-empty">
      咨询记录会保存在此处
    </p>
  </section>
  <div class="workspace-profile">
    <span class="profile-avatar">
      <el-icon>
        <User />
      </el-icon>
    </span>
    <div v-if="!collapsed" class="profile-copy">
      <span>
        我的工作空间
      </span>
      <small>
        会话保存在当前浏览器
      </small>
    </div>
    <slot name="profile-action">
    <el-tooltip content="咨询设置" placement="right">
      <button type="button" class="workbench-icon" aria-label="咨询设置" @click="$emit('settings')">
        <el-icon>
          <SetUp />
        </el-icon>
      </button>
    </el-tooltip>
    </slot>
  </div>
</aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, ChatDotSquare, Reading, Connection, Share, Clock, User, SetUp } from '@element-plus/icons-vue'
import GlyphMark from './GlyphMark.vue'

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  showRecent: { type: Boolean, default: true },
  actionLabel: { type: String, default: '新建咨询' },
  sessions: { type: Array, required: true },
  currentSessionId: { type: String, default: null }
})
defineEmits(['create', 'select', 'manage', 'settings'])
const route = useRoute()
const navigation = [
  { path: '/agent', label: '智能问答', icon: ChatDotSquare },
  { path: '/knowledge', label: '知识库', icon: Reading },
  { path: '/dsl', label: 'DSL 规则', icon: Connection },
  { path: '/graph', label: '知识图谱', icon: Share }
]
const recentSessions = computed(() => [...props.sessions].sort((first, second) => new Date(second.lastActive) - new Date(first.lastActive)).slice(0, 8))
</script>

<style scoped>.workbench-sidebar {
  grid-area: sidebar;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--wb-canvas);
  border-right: 1px solid var(--wb-line);
  overflow: hidden;
}
.workbench-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 88px;
  flex-shrink: 0;
  padding: 0 24px;
  color: var(--wb-blue);
  text-decoration: none;
}
.workbench-brand svg {
  width: 30px;
  height: 36px;
  flex-shrink: 0;
}
.brand-copy {
  display: flex;
  flex-direction: column;
}
.brand-copy strong {
  font: 650 27px/1.1 var(--wb-number);
  letter-spacing: -1px;
}
.brand-copy span {
  font-size: 12px;
  letter-spacing: .6px;
  margin-top: 5px;
  color: var(--wb-muted);
  white-space: nowrap;
}
.new-consultation {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 0 16px 28px;
  padding: 10px 14px;
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
  background: var(--wb-surface);
  color: var(--wb-blue);
  font-size: 14px;
  white-space: nowrap;
}
.new-consultation:hover {
  background: var(--wb-blue-soft);
  border-color: var(--wb-blue);
}
.workspace-navigation {
  padding: 0 12px;
  display: grid;
  gap: 5px;
}
.navigation-label, .recent-heading {
  font-size: 12px;
  color: var(--wb-muted);
}
.navigation-label {
  padding: 0 13px;
  margin-bottom: 6px;
}
.workspace-link {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 43px;
  padding: 0 14px;
  border-radius: 6px;
  text-decoration: none;
  color: var(--wb-muted);
  font-size: 15px;
  white-space: nowrap;
}
.workspace-link .el-icon {
  font-size: 18px;
}
.workspace-link:hover {
  background: var(--wb-blue-soft);
  color: var(--wb-blue);
}
.workspace-link.is-current {
  color: var(--wb-blue);
  background: var(--wb-blue-soft);
  font-weight: 600;
}
.current-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  margin-left: auto;
}
.recent-consultations {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  margin: 24px 12px 0;
  border-top: 1px solid var(--wb-line);
  padding-top: 12px;
}
.recent-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 8px 14px;
}
.recent-session {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 12px 14px;
  border-radius: 6px;
  color: var(--wb-muted);
  position: relative;
  margin-bottom: 5px;
}
.recent-session:hover, .recent-session.is-current {
  background: var(--wb-blue-soft);
}
.recent-session.is-current {
  color: var(--wb-ink);
}
.recent-session.is-current::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  background: var(--wb-blue);
  border-radius: 2px;
}
.session-title, .session-preview {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  width: 100%;
}
.session-title {
  font-size: 14px;
}
.session-preview {
  color: var(--wb-muted);
  font-size: 12px;
}
.sidebar-empty {
  color: var(--wb-muted);
  padding: 8px 14px;
  font-size: 12px;
}
.workspace-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  margin-top: auto;
  border-top: 1px solid var(--wb-line);
}
.profile-avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--wb-border);
  border-radius: 50%;
  color: var(--wb-blue);
  background: var(--wb-blue-soft);
  flex-shrink: 0;
}
.profile-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  font-size: 12px;
}
.profile-copy small {
  color: var(--wb-muted);
  font-size: 11px;
  white-space: nowrap;
}
.workspace-profile .workbench-icon {
  margin-left: auto;
}
.is-collapsed .brand-copy, .is-collapsed .nav-label, .is-collapsed .navigation-label, .is-collapsed .current-dot {
  display: none;
}
.is-collapsed .workbench-brand, .is-collapsed .workspace-link {
  justify-content: center;
  padding: 0;
}
.is-collapsed .new-consultation {
  padding: 12px;
  justify-content: center;
}
.is-collapsed .workspace-profile {
  padding: 16px 0;
  flex-direction: column;
}
.is-collapsed .workspace-profile .workbench-icon {
  margin: 0;
}
</style>
