// 入口：挂路由 + 全局样式。登录态封装在 api/client.ts（fetch 自动带 Bearer / 401 刷新一次）。
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './style.css'

createApp(App).use(router).mount('#app')
