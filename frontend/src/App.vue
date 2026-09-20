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

// adminOnly：系统管理（T-3.12 批 1）仅 admin 可见——前端隐藏只是 UX，后端 403 才是权威
const MENUS = [
  { name: 'overview', label: '总览' },
  { name: 'interfaces', label: '接口' },
  // P1-7①（2026-09-18）：原「异常」「回流看板」都是黑话——前者与「LLM 失败」边界不清
  // （实为 node=request 的接口级错误），后者完全猜不到内容（实为错误聚类 + 回归回流处置）。
  { name: 'anomalies', label: '接口异常' },
  { name: 'llm-failures', label: 'LLM 失败' },
  { name: 'traces', label: '链路查询' },
  { name: 'backflow', label: '错误闭环' },  // P2-6：第六个一级菜单（detail §9.1 登记）
  { name: 'admin-configs', label: '系统管理 · 配置', adminOnly: true },
  { name: 'admin-users', label: '系统管理 · 账号', adminOnly: true },
]

const visibleMenus = computed(() => MENUS.filter((m) => !m.adminOnly || user.value?.role === 'admin'))

// 详情页下钻共用父菜单高亮（trace-detail → 链路查询；backflow-cluster → 错误闭环）
const activeName = computed(() => {
  if (route.name === 'trace-detail') return 'traces'
  if (route.name === 'backflow-cluster') return 'backflow'
  return route.name
})

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
        <router-link class="brand" :to="{ name: 'overview' }">
          <span class="mark" aria-hidden="true" />
          obs 观测台
        </router-link>
        <span class="muted tag">agent 调用链路的错误聚类与回归回流平台</span>
        <span class="spacer" />
        <span class="muted who">{{ user.username }}（{{ user.role }}）</span>
        <button class="btn-ghost" type="button" @click="doLogout">退出</button>
      </div>
      <nav class="menu">
        <router-link
          v-for="m in visibleMenus" :key="m.name"
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

/* v1.15：顶栏改深色。原因 = 此前顶栏底色就是 --bg，与页面底色**完全相同**，
   只靠一条 1px 线分隔 ⇒ 品牌区/菜单/内容三个层次亮度一致，整页没有视觉锚点。
   深底把「导航」与「内容」切成两段，是全站层次感最便宜的一次性来源。 */
/* 深底不用纯色：上浅下深的一档渐变让顶栏有「面板厚度」，
   底部再压一条从透明→品牌蓝→透明的高光线 —— 这是「精密仪器面板」最省的科技感来源，
   且**不引入任何浅色文字**，对比度不受影响（仍然只有 --topbar-text/--topbar-muted 两档前色）。 */
.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(180deg, #1b2536 0%, var(--topbar) 62%, #0f151e 100%);
  box-shadow: inset 0 -1px 0 rgba(37, 99, 235, 0.55), 0 1px 0 rgba(0, 0, 0, 0.25);
  padding: var(--sp-3) 16px 0;
}

/* 高光线：绝对定位贴顶栏底边，两端淡出。pointer-events:none 防挡住菜单点击。 */
.topbar::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background: linear-gradient(90deg,
    transparent 0%, rgba(37, 99, 235, 0.35) 18%, rgba(96, 165, 250, 0.9) 50%,
    rgba(37, 99, 235, 0.35) 82%, transparent 100%);
}

.row-brand {
  max-width: 1240px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--topbar-text);
}

/* 品牌标记：深底上的一枚实心块，给左端起一个视觉支点（纯装饰，aria-hidden）。
   取值见下方 .mark 单一定义处 —— 此处不再重复声明，防两条规则打架。 */

.tag {
  font-size: 12px;
}

.spacer {
  flex: 1;
}

.who {
  font-size: 12px;
}

/* 顶栏内的 .muted / .btn-ghost 必须就地覆盖：这两个是全局类，取值面向浅底，
   直接留在深底上会变成「深灰字配深底」（不可读）。scoped 前缀保证只影响顶栏内部。 */
.topbar .muted {
  color: var(--topbar-muted);
}

.topbar .btn-ghost {
  background: transparent;
  color: var(--topbar-text);
  border-color: rgba(255, 255, 255, 0.22);
}

.topbar .btn-ghost:hover {
  background: var(--topbar-hover);
  border-color: rgba(255, 255, 255, 0.38);
}

.mark {
  width: 10px;
  height: 10px;
  flex: none;
  border-radius: 2px;
  background: linear-gradient(140deg, #60a5fa, var(--brand));
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.9);
}

.menu {
  max-width: 1240px;
  margin: var(--sp-3) auto 0;
  display: flex;
  gap: 6px;
}

/* 深底下放弃原「凸起标签页」隐喻（那靠浅底 + 顶栏同色才成立），
   改为底部指示条：透明下边框常驻占位 ⇒ 选中时只换颜色、不引起位移。 */
.menu-item {
  padding: 9px 16px 10px;
  font-size: 14px;
  letter-spacing: 0.02em;
  color: var(--topbar-muted);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  position: relative;
  transition: background 0.14s, color 0.14s;
}

.menu-item:hover {
  background: var(--topbar-hover);
  color: var(--topbar-text);
}

/* 选中：指示条用两端淡出的渐变 + 微光，与顶栏底部高光线同一种语汇。
   ⚠️ 指示条是**装饰**，选中态的可达性仍由 color:#fff（配深底 15.9:1）+ font-weight:600 承担，
   不依赖颜色渐变 —— 色盲用户与灰度屏上依然可辨。 */
.menu-item.on {
  background: var(--topbar-hover);
  color: #fff;
  font-weight: 600;
}

.menu-item.on::after {
  content: "";
  position: absolute;
  left: 6px;
  right: 6px;
  bottom: 0;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, #60a5fa, transparent);
  box-shadow: 0 0 9px rgba(96, 165, 250, 0.95);
}

.content {
  max-width: 1240px;
  margin: 16px auto 28px;
  padding: 0 16px;
}
</style>
