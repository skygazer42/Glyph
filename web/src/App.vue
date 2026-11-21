<template>
  <el-config-provider :locale="zhCn" :message="{ offset: noticeOffset }">
    <router-view v-if="!$route.meta.workspace" :key="$route.path" />
    <WorkspaceLayout v-else>
      <router-view :key="$route.path" />
    </WorkspaceLayout>
  </el-config-provider>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'

const route = useRoute()
const compactQuery = window.matchMedia('(max-width: 699px)')
const isCompact = ref(compactQuery.matches)
// Messages sit below the compact workbench header or public service identity.
const noticeOffset = computed(() => (route.meta.workspace || isCompact.value ? 64 : 72) + 16)
const updateCompact = event => { isCompact.value = event.matches }
onMounted(() => compactQuery.addEventListener('change', updateCompact))
onBeforeUnmount(() => compactQuery.removeEventListener('change', updateCompact))
</script>
