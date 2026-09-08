// 路由（detail §9.2 三页 + §13.4 正文默认隐藏）。登录态看 localStorage access token。
// 路由守卫：受保护路由无 token → /login；已登录访问 /login → /dashboard。
// 落点（T-2.4，兑现 detail §9.1 v1.11 注）：'/' 与登录后首落 /dashboard，未命中兜底 /dashboard。
import { createRouter, createWebHistory } from 'vue-router'

import { accessToken } from '../api/client'
import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'
import TraceDetailView from '../views/TraceDetailView.vue'
import TracesView from '../views/TracesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true },
    },
    { path: '/traces', name: 'traces', component: TracesView, meta: { requiresAuth: true } },
    {
      path: '/traces/:agent/:traceId',
      name: 'trace-detail',
      component: TraceDetailView,
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const loggedIn = accessToken() !== null
  if (to.meta.requiresAuth && !loggedIn) return { name: 'login' }
  if (to.name === 'login' && loggedIn) return { name: 'dashboard' }
  return true
})

export default router
