import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// 单测配置与 vite.config.ts 分文件：构建配置里加 test 段会让 vite 也去解析
// vitest 的类型/依赖，且 dev proxy 等运行时选项对测试无意义。
// 不引 alias（本仓 tsconfig 无 paths，源码一律相对导入），与构建解析规则保持一字不差。
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    // 组件测试里组件用原生 fetch：默认 node 环境无 window/localStorage，jsdom 才有
    restoreMocks: true,
  },
})
