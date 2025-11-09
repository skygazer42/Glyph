<template>
  <div id="app">
    <el-container style="height: 100vh">
      <el-header>
        <div class="header-content">
          <h1>🏛️ 政策DSL生成和知识库管理系统</h1>
          <el-menu
            mode="horizontal"
            :default-active="$route.path"
            router
          >
            <el-menu-item index="/agent">
              <el-icon><ChatDotRound /></el-icon>
              AI问答
            </el-menu-item>
            <el-menu-item index="/dsl">
              <el-icon><Document /></el-icon>
              DSL生成
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><Collection /></el-icon>
              知识库管理
            </el-menu-item>
          </el-menu>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { Document, Collection, ChatDotRound } from '@element-plus/icons-vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.el-header {
  background-color: #545c64;
  color: white;
  padding: 0;
}

.header-content {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 20px;
}

.header-content h1 {
  font-size: 20px;
  margin-right: 30px;
  white-space: nowrap;
}

.el-menu.el-menu--horizontal {
  border-bottom: none;
  background-color: transparent;
}

.el-menu--horizontal > .el-menu-item {
  color: rgba(255, 255, 255, 0.8);
  border-bottom: 2px solid transparent;
}

.el-menu--horizontal > .el-menu-item:hover,
.el-menu--horizontal > .el-menu-item.is-active {
  color: white;
  border-bottom-color: white;
  background-color: rgba(255, 255, 255, 0.1);
}

.el-main {
  padding: 20px;
  background-color: #f5f5f5;
}
</style>
