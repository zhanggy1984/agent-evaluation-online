// 路由（detail §9.2 三页 + §13.4 正文默认隐藏）。登录态看 localStorage access token。
// 路由守卫：受保护路由无 token → /login；已登录访问 /login → /traces。
// 注（本批决定）：detail §9.1 远期落点为 /dashboard（阶段 2），本批登录后先落 /traces。
import { createRouter, createWebHistory } from 'vue-router'

import { accessToken } from '../api/client'
import LoginView from '../views/LoginView.vue'
import TraceDetailView from '../views/TraceDetailView.vue'
import TracesView from '../views/TracesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/traces' },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/traces', name: 'traces', component: TracesView, meta: { requiresAuth: true } },
    {
      path: '/traces/:agent/:traceId',
      name: 'trace-detail',
      component: TraceDetailView,
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/traces' },
  ],
})

router.beforeEach((to) => {
  const loggedIn = accessToken() !== null
  if (to.meta.requiresAuth && !loggedIn) return { name: 'login' }
  if (to.name === 'login' && loggedIn) return { name: 'traces' }
  return true
})

export default router
