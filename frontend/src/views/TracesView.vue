<script setup lang="ts">
// 链路查询页（一级菜单"链路查询"，IA 重构 v1.13 接壳）：trace_id / keyword 可任一
// （都空 = 当前时间窗内全部命中），agent 过滤。检索走 ≤200 上限；红显 = status∈{error,timeout}。
// Q6 决策：agent 过滤由自由文本框改为共享动态下拉（全站 + /metrics/agents 实测列表）。
// P1-10 后半（2026-09-20）：此前时间窗**没有前端控件**（「近 7 天」只在空态里出现一次）
// ⇒ 7d 全量超 200 上限时，后端错误消息要求「缩小范围」，而页面上没有任何时间维度可缩小。
// ⚠️ 档位常量复用指标页的 `WINDOWS`，但**只 import 常量、不碰它的单例 state**：
// P1-11 用户拍板「跨页窗口不共享」，链路页的窗必须与指标页各自独立，否则互相拖拽。
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { listTraces } from '../api/traces'
import { agentDisplay, useAgents } from '../composables/useAgents'
import { WINDOWS, type WindowKey } from '../composables/useMetricFilter'
import type { TraceListItem } from '../api/types'

const router = useRouter()
const route = useRoute()

// P1-11（2026-09-18）：本页原**完全不读 URL** ⇒ 「从别处带着筛选跳过来」做不到。
// 现从 route.query 初始化 —— 接口页的错误数就是这么跳进来的（带 interface + status）。
// ⚠️ 这两个筛选**没有对应的表单控件**，故模板里渲染了「当前筛选」提示条：否则用户会
// 看到一个说不清为什么这么少的条数，这是本页最容易被误判成 bug 的形态。
const qs = (k: string): string => String(route.query[k] ?? '')
const queryForm = ref({
  trace_id: qs('trace_id'), keyword: qs('keyword'), agent: qs('agent'), interface: qs('interface'),
})
const statusFilter = ref(qs('status'))
const loading = ref(false)
const errorMsg = ref('')
const items = ref<TraceListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const DEEP_PAGE_LIMIT = Math.ceil(200 / pageSize) // §14.4 深翻页上限 200 → 前端最多 10 页
// P1-10 后半：时间窗档位（默认 7d = 改动前行为，进页观感不变）。
// ⚠️ 毫秒在**前端本地算**，刻意**不读 `keyword_search_days`** —— 那个键是运行时配置，
// 若跟随它，档位名会与实际窗不符（管理员把它改成 3d 时，「近 7 天」这个按钮就开始撒谎）。
// 代价：链路页不再跟随该配置；换来的是**名字与行为始终一致**。
const win = ref<WindowKey>('7d')
const WIN_MS: Record<WindowKey, number> = { '1h': 3600e3, '24h': 86400e3, '7d': 7 * 86400e3 }
/** 当前档位中文名（供空态 / 提示条引用）。档位本身已由上方下拉常显 ⇒ 不再另加状态栏。 */
const winLabel = computed(() => WINDOWS.find((w) => w.v === win.value)?.label ?? '')
// P1-10：分母此前恒等于上式（写死 10），total 小于 200 时也显示「x / 10」
// ⇒ 用户会以为还有 9 页可翻。真实可翻页数 = min(上限, ceil(total/pageSize))，且至少 1 页。
const maxPages = computed(() =>
  Math.max(1, Math.min(DEEP_PAGE_LIMIT, Math.ceil(total.value / pageSize))))

const { agents, loading: agentsLoading, errorMsg: agentsError, load: loadAgents } = useAgents()

function fmtTs(ts: number | null): string {
  if (!ts) return '-'
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function redFlag(row: TraceListItem): boolean {
  return row.status === 'error' || row.status === 'timeout'
}

function pickAgent(v: string): void {
  queryForm.value.agent = v
}

/** 切时间窗 = 换检索范围 ⇒ **必须回第 1 页**，否则会停在旧范围算出的、现已越界的页码上。
 *  形参与 `pickAgent` 同形（收 string、内部收窄），免得模板里写类型断言。 */
function pickWindow(v: string): void {
  const k = WINDOWS.find((w) => w.v === v)?.v
  if (!k || win.value === k) return
  win.value = k
  void doSearch(1)
}

async function doSearch(p = 1): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const q = {
      trace_id: queryForm.value.trace_id.trim() || undefined,
      keyword: queryForm.value.keyword.trim() || undefined,
      agent: queryForm.value.agent.trim() || undefined,
      interface: queryForm.value.interface.trim() || undefined,
      status: statusFilter.value.trim() || undefined,
      // 每次查询都按**当刻**重算窗起点（不缓存），否则页面开久了窗会悄悄前移。
      start_ts: Date.now() - WIN_MS[win.value],
      page: p,
      page_size: pageSize,
    }
    const res = await listTraces(q)
    items.value = res.items
    total.value = res.total
    page.value = p
  } catch (e) {
    if (e instanceof ApiError) {
      errorMsg.value = `查询失败（${e.code}）：${e.message}`
      items.value = []
    } else {
      throw e
    }
  } finally {
    loading.value = false
  }
}

function resetAndSearch(): void {
  void doSearch(1)
}

/** 清掉「从别处带过来」的隐形筛选（interface / status）—— 它们没有表单控件可改，只能整块清 */
function clearInheritedFilters(): void {
  queryForm.value.interface = ''
  statusFilter.value = ''
  void doSearch(1)
}

function rowKey(row: TraceListItem): string {
  // 折叠列表一行 = (agent, trace_id) 唯一；字段可空 → 拼接兜底成稳定字符串 key
  return `${row.agent ?? ''}#${row.trace_id ?? ''}`
}

function toDetail(row: TraceListItem): void {
  if (row.agent && row.trace_id) {
    void router.push({ name: 'trace-detail', params: { agent: row.agent, traceId: row.trace_id } })
  }
}

function retryAgents(): void {
  void loadAgents(true)
}

onMounted(() => {
  void loadAgents()
  void doSearch(1)
})
</script>

<template>
  <div>
    <form class="panel query" @submit.prevent="resetAndSearch">
      <input v-model="queryForm.trace_id" placeholder="trace_id（精确）" />
      <input v-model="queryForm.keyword" placeholder="错误关键字" />
      <label class="agent-field">
        <select
          :value="queryForm.agent"
          class="sel" @change="pickAgent(($event.target as HTMLSelectElement).value)"
        >
          <option value="">全站 agent</option>
          <option v-for="a in agents" :key="a" :value="a">{{ agentDisplay(a) }}</option>
        </select>
        <span v-if="agentsLoading" class="muted hint">载入中…</span>
        <button v-else-if="agentsError" class="link-like" type="button" @click="retryAgents">
          agent 列表重试
        </button>
      </label>
      <!-- P1-10 后半：时间窗。默认 7d = 改动前行为；用户可主动收到 1h / 24h，
           这样后端那条「检索深度上限 200，请缩小范围」终于有了对应的 UI 动作。 -->
      <label class="agent-field">
        <select
          :value="win"
          class="sel" @change="pickWindow(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="w in WINDOWS" :key="w.v" :value="w.v">{{ w.label }}</option>
        </select>
      </label>
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? '查询中…' : '查询' }}
      </button>
    </form>

    <!-- P1-11：status / interface 没有表单控件 ⇒ 必须显式告诉用户「你正被什么筛着」，
         否则条数少得像 bug。散文里的口径提示是**认领**，不是装饰。
         ⚠️ 口径差异有**三个**独立成因，缺一个都会让用户认定提示条在胡说：
           ① 时间窗：接口页的窗由该页筛选条决定（进页默认 24h），本页由**本页自己的档位下拉**决定
              （P1-10 后半补上；此前无控件、恒为后端默认值）—— 两页**互不联动**（P1-11 用户拍板）。
           ② 折叠去重：本页 trace_key 折叠 ⇒ 倾向于**更少**
           ③ 节点范围：接口页只看 node=request，本页不限 ⇒ 倾向于**更多**
         ⚠️ 2026-09-18 此处曾写「24h 显示 2 → 本页 120，60 倍」——**该论据已作废**：
           当时 listTraces 没把 status 发进 URL（见 api/traces.ts），120 是「不限 status」的
           条数，与窗口无关。修复后的正确量级（API 直连控制变量，同一时刻同一库）：
             同窗 24h：接口页 2  | 本页 2   ← **逐字相等**
             同窗 7d ：接口页 7  | 本页 29
             跨窗    ：接口页 24h 2 → 本页 7d 29 = 14.5×
           ⇒ 窗口确实是最大的一维（同窗时另两维在 24h 内不显著），但**依据是同窗对照，
           不是那个 60 倍**；「同窗对照」是拆这类差异的唯一手法，别拿跨窗读数直接归因。
           数字会随时间腐，改文案时不要把它们抄进 UI。
         文案里**不许写死「接口页 = 24h」**：用户在接口页可以切 7d，写死就会腐。 -->
    <p v-if="statusFilter || queryForm.interface" class="filter-hint">
      <span>当前筛选：</span>
      <span v-if="queryForm.interface">接口 <code>{{ queryForm.interface }}</code></span>
      <span v-if="statusFilter">状态 <code>{{ statusFilter }}</code></span>
      <span class="muted">
        （本页按上方时间窗 {{ winLabel }}、按 trace 去重、不限节点；接口页按它自己的时间窗、
        按事件计数 ⇒ 条数通常不相等）
      </span>
      <button class="link-like" type="button" @click="clearInheritedFilters">清除筛选</button>
    </p>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>

    <div class="panel list">
      <p class="muted" v-if="!loading && items.length === 0">无命中 trace（{{ winLabel }}检索窗；可切换上方时间窗，或缩小 trace_id / keyword 重试）</p>
      <table v-else>
        <thead>
          <tr>
            <th>时间</th>
            <th title="产生该事件的智能体名（good-question / contract-check / smart-procurement / customer-service）">agent</th>
            <th title="一次请求链路的唯一标识：同一 trace_id 的所有事件属同一次调用">trace_id</th>
            <th>接口</th>
            <th>最近节点</th>
            <th>状态</th>
            <th>错误</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in items"
            :key="rowKey(row)"
            :class="{ red: redFlag(row) }"
            @click="toDetail(row)"
          >
            <td>{{ fmtTs(row.ts) }}</td>
            <td>{{ agentDisplay(row.agent) }}</td>
            <td class="mono">{{ row.trace_id }}</td>
            <td>{{ row.interface }}</td>
            <td>{{ row.node }}</td>
            <td>{{ row.status }}</td>
            <td class="err">{{ row.error_type || row.error_msg || '' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="foot">
        <span class="muted">共 {{ total }} 条 trace（检索深度上限 200）</span>
        <span v-if="total > pageSize">
          <button
            class="btn-ghost" type="button" :disabled="page <= 1" @click="doSearch(page - 1)"
          >上一页</button>
          <span class="page-no">{{ page }} / {{ maxPages }}</span>
          <button
            class="btn-ghost" type="button"
            :disabled="page >= maxPages || items.length < pageSize"
            @click="doSearch(page + 1)"
          >下一页</button>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.query {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.query input {
  flex: 1;
  min-width: 140px;
}

.agent-field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sel {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
}

.hint {
  font-size: 12px;
}

/* P1-11：隐形筛选提示条（interface / status 无表单控件可改，只能整块清） */
.filter-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
}

.filter-hint code {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  color: var(--brand);
}

.link-like {
  border: none;
  background: none;
  padding: 0;
  color: var(--brand);
  font-size: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  text-align: left;
  padding: 7px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

th {
  color: var(--muted);
  font-weight: 500;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover {
  background: var(--hover-row);
}

tr.red td:first-child {
  box-shadow: inset 3px 0 0 var(--error);
}

.err {
  color: var(--error);
  word-break: break-all;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
}

.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.page-no {
  margin: 0 8px;
  color: var(--muted);
}
</style>
