<script setup lang="ts">
// 布局壳（前端 IA 重构 v1.13）：品牌/用户/退出在首行，二级菜单吸顶条在次行，内容经 <router-view/>。
// auth 过期广播仍在此监听（api/client.ts 终局 401 → 回登录页）。菜单高亮按当前路由名命中。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { logout } from './api/auth'
import { AUTH_EXPIRED_EVENT, readStoredUser } from './api/client'

const route = useRoute()
const router = useRouter()

// readStoredUser() 读 localStorage 非响应式 → 存 ref，登录/登出后随路由跳转变更新
const user = ref(readStoredUser())
watch(() => route.fullPath, () => { user.value = readStoredUser() })

const MENUS = [
  { name: 'overview', label: '总览' },
  { name: 'interfaces', label: '接口' },
  { name: 'anomalies', label: '异常' },
  { name: 'llm-failures', label: 'LLM 失败' },
  { name: 'traces', label: '链路查询' },
]

// 详情页/链路查询共用 traces 高亮（trace-detail 落在链路查询下）
const activeName = computed(() => (route.name === 'trace-detail' ? 'traces' : route.name))

function isActive(name: string): boolean {
  return activeName.value === name
}

async function doLogout(): Promise<void> {
  await logout()
  void router.push({ name: 'login' })
}

function onExpired(): void {
  void router.push({ name: 'login' })
}

onMounted(() => window.addEventListener(AUTH_EXPIRED_EVENT, onExpired))
onUnmounted(() => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired))
</script>

<template>
  <div class="shell">
    <header v-if="user" class="topbar">
      <div class="row-brand">
        <router-link class="brand" :to="{ name: 'overview' }">obs 观测台</router-link>
        <span class="muted tag">agent-evaluation-online</span>
        <span class="spacer" />
        <span class="muted who">{{ user.username }}（{{ user.role }}）</span>
        <button class="btn-ghost" type="button" @click="doLogout">退出</button>
      </div>
      <nav class="menu">
        <router-link
          v-for="m in MENUS" :key="m.name"
          class="menu-item" :class="{ on: isActive(m.name) }"
          :to="{ name: m.name }"
        >{{ m.label }}</router-link>
      </nav>
    </header>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  padding: 10px 16px 0;
}

.row-brand {
  max-width: 1240px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}

.tag {
  font-size: 12px;
}

.spacer {
  flex: 1;
}

.who {
  font-size: 12px;
}

.menu {
  max-width: 1240px;
  margin: 8px auto 0;
  display: flex;
  gap: 4px;
}

.menu-item {
  padding: 7px 14px;
  font-size: 14px;
  color: var(--muted);
  border-radius: 6px 6px 0 0;
  border: 1px solid transparent;
  border-bottom: none;
  transition: background 0.12s;
}

.menu-item:hover {
  background: var(--panel);
  color: var(--text);
}

.menu-item.on {
  background: var(--panel);
  color: var(--brand);
  font-weight: 600;
  border-color: var(--border);
}

.content {
  max-width: 1240px;
  margin: 14px auto 24px;
  padding: 0 16px;
}
</style>
