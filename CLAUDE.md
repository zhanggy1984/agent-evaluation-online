# CLAUDE.md（agent-evaluation-online）

> **本文件只放「每次会话必载」的硬约束与配方** —— 收录判据是「不知道会不会白干一轮」。
> 架构 / 目录 / 质量基线看 `CONTRIBUTING.md`；方案与设计看 `solution.md` / `solution_detail.md` / `task.md`；
> 历史决策与坑看 memory。**通用协作约定不在此**，在全局 `~/.claude/CLAUDE.md`。
>
> ⚠️ 本文件**只写本仓特有、且已经实际踩过**的坑。写之前先问「不做会出什么**具体**故障」。

## 一、改完「没生效」时先看这张表

**三个容器的失效机制不同，别套用同一条结论。**

⚠️ **2026-09-20 批 37 踩到：worker 是独立容器 `obs-worker`（不是 backend 里的一段）** ——
重启 `backend` 对 worker 里跑的 job **零作用**；而**日志也分容器**（`docker compose logs backend`
里只有 HTTP 访问日志、**一条 job 日志都没有**，那正是「worker 不在这个容器里」的判据）。
批 37 为此白跑一轮取证（以为「改了没生效」）。

| 改了什么 | 为什么没生效 | 正确动作 |
|---|---|---|
| 前端 | `obs-frontend` 是**多阶段构建的 baked 镜像**（`docker inspect -f '{{.Mounts}}' obs-frontend` ⇒ `[]`，**无 bind mount**）⇒ 宿主 build 不出现在容器里 | `docker compose build frontend && docker compose up -d --force-recreate frontend`；也可 `docker cp` 产物进容器（批 6 用过） |
| 后端 API | `obs-backend` **有** bind mount（`./backend:/app`），但 uvicorn **没带 `--reload`** ⇒ **文件是新的、进程跑的是旧代码** | 重启进程：`docker compose restart backend`。⚠️ 「文件在容器里」**不等于**「改动生效」 |
| 后端 **job**（worker/*.py） | 跑在**另一个容器** `obs-worker` 里（同 bind mount、同样无 `--reload`） | `docker compose restart worker`。⚠️ **`docker compose ps` 先看有几个 service**，别默认「后端 = 一个容器」 |
| 真机取证 | **旧标签页的模块级单例早已加载**（如 `useAgents` 的 `displayMap`）⇒ 在旧页上看等于没验 | **必须新开标签页**再验 |
| 删容器内文件（`docker exec <容器> rm <文件>`） | 文件属主不是默认 exec 用户 —— `obs-backend` 默认跑 `appuser`，而 `/tmp` 下的探针常属 `root` ⇒ **`Operation not permitted`**（是**没做成**，不是没生效） | 加 `-u root`：`docker exec -u root <容器> rm <文件>`。⚠️ 别误判成「路径写错了」去反复核对路径 |

## 二、真机取证的纪律（本项目反复踩过）

- **新开标签页**（同上）。取证前先问「我这个页面是什么时候加载的」。
- **改筛选 ≠ 发请求**：`MetricFilterBar` 的 `pickAgent()`（`frontend/src/components/MetricFilterBar.vue:30-32`）
  只写 `filter.agent`、**不发请求**；查询由 `:72` 的按钮 `$emit('refresh')` 触发
  ⇒ 验证动作是「**改 select + 点刷新**」两步，只 dispatch change 会误判成「没生效」。
- **要读实际请求 URL**，不能只看渲染结果 —— 本仓出过「参数没进 URL、过滤静默失效」的假绿（P1-11）。

## 三、构建与测试

- **前端**（`frontend/`）：`npx vitest run`；`npm run build`（含 `vue-tsc --noEmit`）。
  ⚠️ tsconfig 的 `lib` **不含 es2022** ⇒ 别用 `Array.prototype.at()`，会卡在类型检查那一步。
- **后端**（`backend/`）：`backend/.venv` 已存在；pytest 配置在 `backend/pyproject.toml` 的
  `[tool.pytest.ini_options]`。新增 async 测试**必须自管 session/事务**，严禁跨测试共享连接。

## 四、数据面坐标（写探针前先对）

- **MySQL**：容器 `shared-mysql`，库名 **`dev.obs`**（不是 `obs`）；宿主端口 `33061`。
  ⚠️ 表名易猜错：簇表叫 **`error_cluster`**（不是 `backflow_cluster`）。
- **ES**：`http://localhost:39200`，容器 `shared-elasticsearch`。
  后端的检索面 = **`dev.obs-event-*` + `dev.obs-log-*` 两个索引**（见 `backend/app/store/es.py::index_patterns`）。
  ⚠️ **只查其中一个会得到偏小的数**（2026-09-20 实证：只查 `log` 得 417，实际 1952）——
  下结论前先确认「我量的索引集」与「后端用的索引集」是不是同一个。

## 五、提交与工具

- **pre-commit 会跑**（静态检查 + 覆盖率门禁）。若被拦下说「改了代码没配套测试」，**该理由成立，去补测**，别绕过。
- Bash 工具是 **Git Bash，不是 PowerShell** ⇒ 多行 commit message 用
  `git commit -F - <<'EOF'`，**不要用 here-string `@'…'@`**（会**静默**污染 message，
  且 pre-commit **不校验 message**、照报「通过」）。提交后 `cat -A` 核对首尾。
- 查 `.env` **只 grep 键名**，绝不把含 secret 的键拼进同一模式（命中行会被打进会话记录）。

## 六、memory 维护

memory 目录：`C:\Users\Administrator\.claude\projects\D--study-aiprojcet-agent-evaluation-online\memory\`

**每次增删正文文件后，必须当场跑索引复核**（`MEMORY.md` 头部写死了这条纪律），**输出必须为空**：

```bash
D="<memory dir>"; comm -23 \
  <(ls "$D"/*.md | xargs -n1 basename | grep -v '^MEMORY.md$' | sed 's/\.md$//' | sort) \
  <(grep -oE '\[\[[a-z0-9-]+\]\]|\]\([a-z0-9-]+\.md\)' "$D/MEMORY.md" | sed -E 's/\[\[(.*)\]\]/\1/; s/\]\((.*)\.md\)/\1/' | sort -u)
```

⚠️ **不要数索引行数** —— 索引按「桶」合并过，**行数 ≠ 文件数**；上面这条（每个正文文件都被引用到）才是判据。
