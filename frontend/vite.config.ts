import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev 热更代理：/api → backend（容器 8000 / 宿主映射见 compose.infra.dev.yml）。
// 生产走 nginx 反代（frontend/nginx.conf /api/ → backend:8000），vite 仅服务本地热更。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
