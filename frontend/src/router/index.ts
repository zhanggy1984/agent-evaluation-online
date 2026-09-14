// 路由（IA 重构 v1.13）：五个一级菜单各一页——总览(/dashboard 落点) / 接口 / 异常 / LLM 失败 /
// 链路查询；trace 详情 /traces/:agent/:traceId 下钻。登录态看 localStorage access token。
// 守卫：受保护路由无 token → /login；已登录访问 /login → 总览。
// 落点：'/' 与登录后首落 /dashboard（总览），未命中兜底 /dashboard。
import { createRouter, createWebHistory } from 'vue-router'

import { accessToken } from '../api/client'
import AdminAgentsView from '../views/AdminAgentsView.vue'
import AdminConfigsView from '../views/AdminConfigsView.vue'
import AdminUsersView from '../views/AdminUsersView.vue'
import AnomaliesView from '../views/AnomaliesView.vue'
import BackflowClusterDetailView from '../views/BackflowClusterDetailView.vue'
import BackflowView from '../views/BackflowView.vue'
import InterfacesView from '../views/InterfacesView.vue'
import LlmFailuresView from '../views/LlmFailuresView.vue'
import LoginView from '../views/LoginView.vue'
import OverviewView from '../views/OverviewView.vue'
import TraceDetailView from '../views/TraceDetailView.vue'
import TracesView from '../views/TracesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/dashboard',
      name: 'overview',
      component: OverviewView,
      meta: { requiresAuth: true },
    },
    {
      path: '/interfaces',
      name: 'interfaces',
      component: InterfacesView,
      meta: { requiresAuth: true },
    },
    {
      path: '/anomalies',
      name: 'anomalies',
      component: AnomaliesView,
      meta: { requiresAuth: true },
    },
    {
      path: '/llm-failures',
      name: 'llm-failures',
      component: LlmFailuresView,
      meta: { requiresAuth: true },
    },
    { path: '/traces', name: 'traces', component: TracesView, meta: { requiresAuth: true } },
    {
      path: '/traces/:agent/:traceId',
      name: 'trace-detail',
      component: TraceDetailView,
      meta: { requiresAuth: true },
    },
    // 回流看板（P2-6 T-3.7）：列表 + 独立详情壳（detail §9.2 独立路由形态）
    { path: '/backflow', name: 'backflow', component: BackflowView, meta: { requiresAuth: true } },
    {
      path: '/backflow/clusters/:clusterId',
      name: 'backflow-cluster',
      component: BackflowClusterDetailView,
      meta: { requiresAuth: true },
    },
    // 系统管理（T-3.12 批 1 / detail §8.6）：admin-only。守卫只判登录态（无角色守卫，
    // 与既有页面同口径）——非 admin 直连此路径由后端 403 拦下，前端隐藏菜单只是 UX。
    {
      path: '/admin/configs',
      name: 'admin-configs',
      component: AdminConfigsView,
      meta: { requiresAuth: true },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: AdminUsersView,
      meta: { requiresAuth: true },
    },
    {
      path: '/admin/agents',
      name: 'admin-agents',
      component: AdminAgentsView,
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const loggedIn = accessToken() !== null
  if (to.meta.requiresAuth && !loggedIn) return { name: 'login' }
  if (to.name === 'login' && loggedIn) return { name: 'overview' }
  return true
})

export default router
