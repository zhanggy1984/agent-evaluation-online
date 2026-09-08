# frontend

> obs 观测台前端。T-1.6 由静态占位升级为 **Vue 3 + Vite + TypeScript** 真工程（栈裁定见
> `solution_detail.md` §9/修订记录；原文档「React」措辞已随栈裁定改 Vue）。
> 只经 backend API（无直连 ES/MySQL，detail §1.1）；页面与路由规格 detail §9.2。

## 三页（detail §9.2 / 本批范围）

| 路由 | 页面 | 数据源 |
|---|---|---|
| `/login` | 登录（admin/viewer） | `POST /api/v1/auth/login`（detail §8.1） |
| `/traces` | 链路查询：trace_id / keyword / agent 过滤 + 分页列表 | `GET /api/v1/traces`（§8.2） |
| `/traces/:agent/:traceId` | 事件树时间轴（parent 缩进）+ error/timeout 红显 + llm_call 高亮 + 日志懒加载 | `GET /api/v1/traces/{agent}/{trace_id}[/logs]` |

## 技术栈与约定

- Vue 3.5 + vue-router 4.5 + Vite 6 + TS（strict）。骨架期不引组件库，手写轻量 CSS。
- 登录态：localStorage（`obs_access` / `obs_refresh` / `obs_user`）；请求自动带
  `Authorization: Bearer <access>`；401 → 用 refresh 单飞刷新一次重试，仍失败清态回 `/login`
  （`src/api/client.ts`；Authorization 头名与存储 medium 为本批实现决定，见 detail 修订记录）。
- 正文两层保护（§8.2 注 v1.1）：请求不带 `body_search` → 后端已把 `input/output/log_message`
  置空，前端零渲染兜底，不另做展示开关。

## 开发 / 构建

- dev 热更：`npm run dev`（vite 反代 `/api` → 后端，`vite.config.ts` 的 `VITE_API_TARGET`）。
- 类型检查：`npm run type-check`（vue-tsc）。构建：`npm run build` → `dist/`。
- 部署：多阶段 `Dockerfile`（node:20-alpine 构建 → nginx:alpine 托管），见 `nginx.conf`。
