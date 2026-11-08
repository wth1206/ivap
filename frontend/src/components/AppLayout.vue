<template>
  <el-container class="app-shell">
    <el-aside width="224px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">IV</div>
        <div>
          <strong>IVAP</strong>
          <span>智能视觉分析平台</span>
        </div>
      </div>

      <el-menu :default-active="activeMenu" router class="nav-menu">
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon><span>系统首页</span>
        </el-menu-item>
        <el-menu-item index="/detect">
          <el-icon><Aim /></el-icon><span>图像检测</span>
        </el-menu-item>
        <el-menu-item index="/analysis">
          <el-icon><DataAnalysis /></el-icon><span>智能分析</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon><span>知识库</span>
        </el-menu-item>
        <el-menu-item index="/agent">
          <el-icon><ChatDotRound /></el-icon><span>Agent 对话</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon><span>历史任务</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <span>ECE-YOLO · RAG · Agent</span>
        <span class="version">v0.1.0</span>
      </div>
    </el-aside>

    <el-container class="content-shell">
      <el-header class="topbar">
        <div class="topbar-title">
          <span class="eyebrow">WORKSPACE</span>
          <strong>{{ route.meta.title || '系统首页' }}</strong>
        </div>
        <div class="topbar-actions">
          <el-tooltip :content="healthDetail" placement="bottom">
            <el-tag :type="app.healthTag" effect="light" round>
              <span class="status-dot" :class="app.health?.status === 'ok' ? 'ok' : 'warn'" />
              {{ app.healthText }}
            </el-tag>
          </el-tooltip>
          <el-button text :icon="Refresh" :loading="app.loading" @click="app.fetchHealth()">
            刷新状态
          </el-button>
        </div>
      </el-header>

      <el-main class="main-area">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Aim,
  ChatDotRound,
  Clock,
  Collection,
  DataAnalysis,
  HomeFilled,
  Refresh,
} from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const app = useAppStore()

const activeMenu = computed(() => {
  if (route.path === '/') return '/'
  return `/${route.path.split('/')[1]}`
})

const healthDetail = computed(() => {
  const health = app.health
  if (!health) return '无法连接后端，请确认服务已启动'
  const database = health.components?.database?.status || '-'
  const detector = health.components?.detector?.status || '-'
  const llm = health.components?.llm?.configured ? '已配置' : '未配置'
  const vectors = health.components?.vector_store?.vectors ?? 0
  return `数据库: ${database} · 模型: ${detector} · LLM: ${llm} · 向量: ${vectors}`
})

onMounted(() => {
  app.fetchHealth()
  app.startPolling()
})
onUnmounted(() => app.stopPolling())
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: var(--ivap-bg);
}
.sidebar {
  background: #0f172a;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 18px 12px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 22px;
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(135deg, #2563eb, #06b6d4);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 13px;
  letter-spacing: -0.03em;
}
.brand strong {
  display: block;
  font-size: 17px;
  letter-spacing: 0.04em;
}
.brand span {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 10.5px;
}
.nav-menu {
  border: none;
  background: transparent;
  flex: 1;
}
.nav-menu :deep(.el-menu-item) {
  color: #cbd5e1;
  border-radius: 10px;
  margin: 4px 0;
  height: 44px;
}
.nav-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}
.nav-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.95), rgba(37, 99, 235, 0.65));
  color: #fff;
}
.sidebar-footer {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 8px 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  color: #64748b;
  font-size: 10px;
}
.version {
  color: #94a3b8;
}
.content-shell {
  min-width: 0;
}
.topbar {
  height: 66px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e9eef6;
  padding: 0 26px;
}
.topbar-title {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.eyebrow {
  font-size: 9px;
  color: #94a3b8;
  letter-spacing: 0.2em;
}
.topbar-title strong {
  font-size: 15px;
  color: #0f172a;
}
.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
}
.status-dot.ok { background: #16a34a; }
.status-dot.warn { background: #d97706; }
.main-area {
  padding: 24px 26px 40px;
  max-width: 1560px;
  width: 100%;
  margin: 0 auto;
}
@media (max-width: 1100px) {
  .sidebar { width: 184px !important; }
  .topbar { padding: 0 16px; }
  .main-area { padding: 18px 16px 32px; }
}
</style>
