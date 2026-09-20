<script setup lang="ts">
// trace 详情页：事件树（后端 seq asc 返回 = §11.1 创建序拓扑，根锚点恒首位；parent 链算缩进层级）。
// 红显 = status∈{error,timeout}；llm_call 高亮 = node=="llm_call"。
// 正文（2026-09-20 改）：log_message 已由 traceLogs() 显式带 body_search=true 放行（见 api/traces.ts）。
// input/output 仍受门控，且本页**没有**它们的渲染点 —— 故未放开（理由同 traces.ts 注释）。
// 日志懒加载：/logs 分页拉（后端 default page_size=50）。
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, readStoredUser } from '../api/client'
import { traceDetail, traceLogs } from '../api/traces'
import type { TraceEventRow, TraceLogRow } from '../api/types'
import { agentDisplay, useAgents } from '../composables/useAgents'
import { errorDetail } from '../traceLabels'

// 正文占位文案随角色变（2026-09-20）：后端门控为 **admin-only**（trace.py「正文门控」）——
// 非 admin 无论是否带 body_search=true，log_message 恒为 None。此时若照旧显示「该行无正文」，
// 就是**把权限问题说成数据问题**：用户会去查「这条日志为什么没有正文」，而真因是角色不足。
const isAdmin = readStoredUser()?.role === 'admin'
const bodyGapText = isAdmin ? '（该行无正文）' : '（正文仅 admin 可见）'

const route = useRoute()
const router = useRouter()

const agent = route.params.agent as string
const traceId = route.params.traceId as string

const loading = ref(true)
const errorMsg = ref('')
const events = ref<TraceEventRow[]>([])
const totalEvents = ref(0)
const truncated = ref(false)

// 日志懒加载状态
const logs = ref<TraceLogRow[]>([])
const logsTotal = ref(0)
const logsPage = ref(0)
const logsLoading = ref(false)
const logsLoaded = ref(false)

// 每行缩进深度：parent 引用的是同 trace 内更早创建的节点（seq 更小）；详情按 seq asc 返回，
// 父先于子 → 顺序遍历即可算深度
interface Row extends TraceEventRow {
  depth: number
  key: string
}

const rows = computed<Row[]>(() => {
  const depthOf: Record<number, number> = {}
  return events.value.map((ev) => {
    let depth = 0
    if (ev.seq != null) {
      if (ev.parent != null && ev.parent in depthOf) {
        depth = depthOf[ev.parent] + 1
      } else {
        depth = 0
      }
      depthOf[ev.seq] = depth
    }
    return { ...ev, depth, key: `e${ev.seq ?? ''}` }
  })
})

function fmtTs(ts: number | null): string {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  const ms = String(d.getMilliseconds()).padStart(3, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${ms}`
}

function statusClass(row: TraceEventRow): string {
  if (row.status === 'error') return 'st-error'
  if (row.status === 'timeout') return 'st-timeout'
  return 'st-ok'
}

function statusLabel(row: TraceEventRow): string {
  if (row.status === 'error') return 'error'
  if (row.status === 'timeout') return 'timeout'
  return row.status || 'ok'
}

function isLlm(row: TraceEventRow): boolean {
  return row.node === 'llm_call'
}

function isRed(row: TraceEventRow): boolean {
  return row.status === 'error' || row.status === 'timeout'
}

function usageText(row: TraceEventRow): string {
  if (!row.usage) return ''
  const u = row.usage as { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }
  const parts: string[] = []
  if (u.prompt_tokens != null) parts.push(`prompt ${u.prompt_tokens}`)
  if (u.completion_tokens != null) parts.push(`completion ${u.completion_tokens}`)
  if (u.total_tokens != null) parts.push(`total ${u.total_tokens}`)
  return parts.join(' · ')
}

async function loadDetail(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await traceDetail(agent, traceId)
    events.value = res.events
    totalEvents.value = res.total
    truncated.value = res.truncated
  } catch (e) {
    if (e instanceof ApiError) {
      errorMsg.value = `加载失败（${e.code}）：${e.message}`
    } else {
      throw e
    }
  } finally {
    loading.value = false
  }
}

async function loadLogs(reset = false): Promise<void> {
  if (logsLoading.value) return
  const target = reset ? 1 : logsPage.value + 1
  logsLoading.value = true
  try {
    const res = await traceLogs(agent, traceId, target, 50)
    logs.value = reset ? res.items : logs.value.concat(res.items)
    logsTotal.value = res.total
    logsPage.value = target
    logsLoaded.value = true
  } catch (e) {
    if (e instanceof ApiError) {
      errorMsg.value = `日志加载失败（${e.code}）：${e.message}`
    } else {
      throw e
    }
  } finally {
    logsLoading.value = false
  }
}

function back(): void {
  void router.push({ name: 'traces' })
}

// 详情页没有 agent 下拉（displayMap 无人触发加载）⇒ 本页自己拉一次，否则中文名恒为空转。
// 单例内部已做「已有结果不重复拉」短路，从列表页进来时不会多打一次请求。
// 日志首屏随详情一起拉（2026-09-20：原为「加载日志」按钮手动触发）。
onMounted(() => { void loadDetail(); void loadLogs(true); void useAgents().load() })
</script>

<template>
  <div>
    <header class="bar">
      <button class="btn-ghost" type="button" @click="back">← 返回列表</button>
      <strong class="title">
        trace <span class="mono">{{ traceId }}</span>
        <span class="muted">（agent: {{ agentDisplay(agent) }}）</span>
      </strong>
      <span class="muted">
        {{ events.length }} / {{ totalEvents }} 事件<span v-if="truncated">（超出上限截断）</span>
      </span>
    </header>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else-if="events.length" class="panel">
      <div class="ev-head">
        <span class="col-seq">seq</span>
        <span class="col-node">节点</span>
        <span class="col-iface">接口</span>
        <span class="col-model">model</span>
        <span class="col-usage">usage</span>
        <span class="col-ts">时间</span>
        <span class="col-dur">耗时</span>
        <span class="col-st">状态</span>
      </div>

      <div
        v-for="row in rows"
        :key="row.key"
        class="ev-row"
        :class="{ red: isRed(row), llm: isLlm(row) }"
        :style="{ paddingLeft: `${8 + row.depth * 20}px` }"
      >
        <span class="col-seq mono">{{ row.seq ?? '' }}</span>
        <span class="col-node">
          <span class="node-tag" :class="{ 'node-llm': isLlm(row) }">{{ row.node ?? '' }}</span>
          <span v-if="row.branch != null && row.branch !== 0" class="muted">#[{{ row.branch }}]</span>
        </span>
        <span class="col-iface">{{ row.interface || '' }}</span>
        <span class="col-model muted">{{ row.model || '' }}</span>
        <span class="col-usage muted">{{ usageText(row) }}</span>
        <span class="col-ts mono muted">{{ fmtTs(row.ts) }}</span>
        <span class="col-dur">{{ row.duration_ms != null ? `${row.duration_ms}ms` : '' }}</span>
        <span class="col-st">
          <span class="status" :class="statusClass(row)">{{ statusLabel(row) }}</span>
        </span>

        <div v-if="isRed(row)" class="err-detail">
          {{ errorDetail(row) }}
        </div>
      </div>
    </div>
    <p v-else-if="!loading" class="muted">该 trace 无事件</p>

    <!-- 日志：正文 log_message 由 traceLogs 带 body_search=true 放行（2026-09-20）
         2026-09-20 用户要求：**去掉「加载日志」按钮，进详情页直接拉首屏**。
         ⚠️ 分页的「加载更多」保留 —— 去掉它会让第 2 页起的日志彻底不可达（page_size=50）。 -->
    <div class="panel logs">
      <div class="logs-head">
        <!-- 「应用日志」不是「日志」的同义词改写，是**收窄**（2026-09-20）：本面板只装
             应用自己 logger.* 打印的行，不是「这次请求的记录」——记录是上方的事件网格。
             用户把「日志」读成常识义的「记录」，于是把空态理解成「系统连记录都没有了」。 -->
        <strong>应用日志</strong>
        <span v-if="logsLoading && !logsLoaded" class="muted">加载中…</span>
        <span v-else-if="logsTotal > logs.length" class="muted">
          {{ logs.length }} / {{ logsTotal }} 条
          <button class="btn-ghost" type="button" :disabled="logsLoading" @click="loadLogs(false)">
            {{ logsLoading ? '加载中…' : '加载更多' }}
          </button>
        </span>
        <span v-else-if="logsLoaded" class="muted">{{ logsTotal }} 条</span>
      </div>

      <div v-if="logsLoaded && logs.length" class="log-list">
        <div v-for="lg in logs" :key="`l${lg.seq ?? ''}`" class="log-row">
          <span class="mono muted log-seq">{{ lg.seq }}</span>
          <span class="log-lv muted">{{ lg.log_level || '' }}</span>
          <span class="muted">{{ fmtTs(lg.ts) }}</span>
          <span class="log-body">{{ lg.log_message ?? bodyGapText }}</span>
        </div>
      </div>
      <!-- 空态（2026-09-20）：原为「无日志」。实测本仓约 60% 的 trace 无日志，且几乎全是
           contract-check 的 `GET /api/tasks/{id}` 轮询——该路径不打日志，轮询越勤这类 trace 越多。
           故「无日志」是**常态、不是故障**，但原措辞读起来像数据丢了。 -->
      <p v-else-if="logsLoaded" class="muted">
        本次请求未产生应用日志（事件由 SDK 自动采集、每条请求必有；日志需应用主动打印）
      </p>
    </div>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 12px;
}

.title {
  flex: 1;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
}

/* 事件树：网格头 + 每行一个网格（行内留 error 详情的整行位） */
.ev-head, .ev-row {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.ev-head {
  color: var(--muted);
  font-size: 12px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
}

.ev-row {
  padding-top: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f1f3;
  flex-wrap: wrap;
}

.ev-row:hover {
  background: var(--hover-row);
}

/* llm_call 高亮 + 红显行（§8.2：红显 = status 判，非 error_type 非空）。
   顺序敏感：error/timeout 与 llm_call 重叠时（如 llm_call 自身失败），红应胜过蓝——
   .llm 在前、.red 在后，同特异性后者覆盖，保证红显醒目；纯 ok 的 llm_call 行仍是蓝色高亮。 */
.ev-row.llm {
  background: var(--hl-llm);
}

.ev-row.red {
  background: var(--hl-red);
}

.col-seq { width: 48px; }
.col-node { width: 150px; }
.col-iface { width: 160px; }
.col-model { width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-usage { width: 130px; }
.col-ts { width: 190px; }
.col-dur { width: 70px; }
.col-st { width: 64px; }

.node-tag {
  background: #f0f1f3;
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 12px;
}

.node-llm {
  background: #dbe7fe;
  color: #1a3f8f;
  font-weight: 600;
}

.status {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 3px;
}

.st-error { background: var(--error); color: #fff; }
.st-timeout { background: var(--timeout); color: #fff; }
.st-ok { background: #e7f3e9; color: var(--ok); }

.err-detail {
  width: 100%;
  color: var(--error);
  font-size: 13px;
  padding-left: 58px;
  word-break: break-all;
}

.logs {
  margin-top: 14px;
}

.logs-head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}

.log-row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 3px 0;
  border-bottom: 1px solid #f0f1f3;
}

.log-seq { width: 60px; }
.log-lv { width: 70px; }
.log-body {
  flex: 1;
  color: var(--text);
  word-break: break-all;
}
</style>
