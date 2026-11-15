<template>
  <router-view v-if="$route.path === '/agent'" />
  <WorkspaceLayout v-else>
    <router-view />
  </WorkspaceLayout>
</template>

<script setup>
import WorkspaceLayout from '@/components/workbench/WorkspaceLayout.vue'
</script>
