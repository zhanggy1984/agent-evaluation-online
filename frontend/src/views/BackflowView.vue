<script setup lang="ts">
// 回流看板列表页（P2-6 T-3.7 / detail §9.2，一级菜单"回流看板"）：总览卡 + 筛选 + cluster 表。
// viewer/admin 均可见；二期（弃留墙/quality）在本页零入口（纯未渲染，detail §9.1 注记）。
// 时间戳 = 后端 _iso naive-UTC 字符串 → fmtISO；写面动作放详情页，本页静态 + 手动刷新。
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { backflowClusters, backflowOverview } from '../api/backflow'
import { metricsInterfaces } from '../api/metrics'
import type {
  BackflowByAgent,
  BackflowCluster,
  BackflowOverview,
  BackflowQuery,
} from '../api/types'
import { useAgents } from '../composables/useAgents'
import {
  CLUSTER_STATUS_LABEL,
  LAYER_OPTIONS,
  OFFLINE_STATUS_TEXT,
  STATUS_OPTIONS,
  WATCH_OPTIONS,
} from '../backflowLabels'
import { fmtISO } from '../format'

const router = useRouter()

const overview = ref<BackflowOverview | null>(null)
const overErr = ref('')
const loading = ref(false)
const errorMsg = ref('')
const items = ref<BackflowCluster[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const queryForm = ref({ agent: '', interface: '', layer: '', status: '', watch: '' })
const { agents, loading: agentsLoading, errorMsg: agentsError, load: loadAgents } = useAgents()
// interface 筛选下拉数据源 = /metrics/interfaces 近 7d 实测接口并集（agent 无关的全局并）
const ifaces = ref<string[]>([])
const ifacesLoading = ref(false)

const maxPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function fmtTs(v: string | null | undefined): string {
  return fmtISO(v)
}

function statusLabel(s: string): string {
  return CLUSTER_STATUS_LABEL[s] ?? s
}

function statusCls(s: string): string {
  return `st-${s}`
}

// link 现行态标签：表内优先展示 offline 拉取语义；invalidated 长句行内截断展示
function linkOffline(s: string | null | undefined): string {
  return s ? (OFFLINE_STATUS_TEXT[s] ?? s) : '-'
}

function pickAgent(v: string): void {
  queryForm.value.agent = v
}

async function loadOverview(): Promise<void> {
  overErr.value = ''
  try {
    overview.value = await backflowOverview()
  } catch (e) {
    if (e instanceof ApiError) overErr.value = `总览加载失败（${e.code}）：${e.message}`
    else throw e
  }
}

async function loadIfaces(): Promise<void> {
  ifacesLoading.value = true
  try {
    const r = await metricsInterfaces(null, '7d')
    const seen = new Set<string>()
    for (const row of r.request) if (row.interface) seen.add(row.interface)
    for (const row of r.llm) if (row.interface) seen.add(row.interface)
    ifaces.value = [...seen].sort()
  } catch {
    ifaces.value = [] // 可选筛选：失败留空不影响主体
  } finally {
    ifacesLoading.value = false
  }
}

async function doSearch(p = 1): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const q: BackflowQuery = {
      agent: queryForm.value.agent.trim() || undefined,
      interface: queryForm.value.interface.trim() || undefined,
      layer: queryForm.value.layer || undefined,
      status: queryForm.value.status || undefined,
      watch: queryForm.value.watch || undefined,
      page: p,
      page_size: pageSize,
    }
    const res = await backflowClusters(q)
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

function toDetail(row: BackflowCluster): void {
  void router.push({ name: 'backflow-cluster', params: { clusterId: row.cluster_id } })
}

function toTrace(row: BackflowCluster, ev: Event): void {
  ev.stopPropagation()
  if (row.first_trace_id && row.agent) {
    void router.push({ name: 'trace-detail', params: { agent: row.agent, traceId: row.first_trace_id } })
  }
}

function refresh(): void {
  void loadAgents(true)
  void loadOverview()
  void loadIfaces()
  void doSearch(page.value)
}

onMounted(() => {
  void loadAgents()
  void loadIfaces()
  void loadOverview()
  void doSearch(1)
})

function agentCounts(): BackflowByAgent[] {
  return overview.value?.by_agent ?? []
}
</script>

<template>
  <div>
    <!-- 总览卡：cluster 状态分布 / verify 分布 / to_fix（近似值标注）/ by_agent 小分布 -->
    <section v-if="overview" class="cards">
      <div class="card">
        <strong>cluster 状态</strong>
        <ul class="kv">
          <li v-for="(v, k) in overview.clusters" :key="k">
            <span class="dot" :class="`st-${k}`" />
            <span>{{ statusLabel(k) }}</span><b>{{ v }}</b>
          </li>
        </ul>
      </div>
      <div class="card">
        <strong>link 回查分布</strong>
        <ul class="kv">
          <li v-for="(v, k) in overview.links" :key="k">
            <span>{{ k }}</span><b>{{ v }}</b>
          </li>
        </ul>
      </div>
      <div class="card">
        <strong>待修复集（本地近似 offline 权威集）</strong>
        <p class="tofix">约 {{ overview.to_fix }} 条 link 待回归/已失败</p>
        <p class="muted note">近似值：本平台无 offline 权威集，以「已激活且未过回归」link 数代理</p>
      </div>
      <div class="card grow">
        <strong>待处置（按 agent）</strong>
        <ul v-if="agentCounts().length" class="kv">
          <li v-for="a in agentCounts()" :key="a.agent">
            <span>{{ a.agent }}</span>
            <b>{{ a.open }} 未处置 · {{ a.claim }} 复核中</b>
          </li>
        </ul>
        <p v-else class="muted note">暂无 open/claim cluster</p>
      </div>
    </section>
    <p v-if="overErr" class="error-text">{{ overErr }}</p>

    <form class="panel query" @submit.prevent="resetAndSearch">
      <label class="agent-field">
        <select :value="queryForm.agent" class="sel" @change="pickAgent(($event.target as HTMLSelectElement).value)">
          <option value="">全站 agent</option>
          <option v-for="a in agents" :key="a" :value="a">{{ a }}</option>
        </select>
        <span v-if="agentsLoading" class="muted hint">载入中…</span>
      </label>
      <label class="agent-field">
        <select :value="queryForm.interface" class="sel" @change="queryForm.interface = ($event.target as HTMLSelectElement).value">
          <option value="">全部接口</option>
          <option v-if="ifacesLoading" disabled>载入中…</option>
          <option v-for="i in ifaces" :key="i" :value="i">{{ i }}</option>
        </select>
      </label>
      <label class="agent-field">
        <select :value="queryForm.layer" class="sel" @change="queryForm.layer = ($event.target as HTMLSelectElement).value">
          <option v-for="o in LAYER_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <label class="agent-field">
        <select :value="queryForm.status" class="sel" @change="queryForm.status = ($event.target as HTMLSelectElement).value">
          <option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <label class="agent-field">
        <select :value="queryForm.watch" class="sel" @change="queryForm.watch = ($event.target as HTMLSelectElement).value">
          <option v-for="o in WATCH_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <button class="btn" type="submit" :disabled="loading">{{ loading ? '查询中…' : '查询' }}</button>
      <button class="btn-ghost" type="button" @click="refresh">刷新</button>
    </form>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>

    <div class="panel list">
      <p v-if="!loading && items.length === 0" class="muted">无命中 cluster（可放宽筛选重试）</p>
      <table v-else>
        <thead>
          <tr>
            <th>状态</th>
            <th>agent / 接口</th>
            <th>错误</th>
            <th>input_hash</th>
            <th>代表 trace</th>
            <th>次数</th>
            <th>fix_version</th>
            <th>首现 / 最新</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in items" :key="row.cluster_id" @click="toDetail(row)">
            <td>
              <span class="status" :class="statusCls(row.status)">{{ statusLabel(row.status) }}</span>
              <span class="muted small" v-if="row.generation > 1">gen{{ row.generation }}</span>
            </td>
            <td>
              <div>{{ row.agent }}</div>
              <div class="muted small">{{ row.interface }}</div>
            </td>
            <td class="err">
              <div>{{ row.error_type }}</div>
              <div class="muted small" :title="row.error_msg ?? ''">{{ row.error_msg }}</div>
            </td>
            <td class="mono short" :title="row.input_hash ?? ''">{{ row.input_hash }}</td>
            <td>
              <button
                v-if="row.first_trace_id && row.agent" class="link-like"
                type="button" @click="toTrace(row, $event)"
              >{{ row.first_trace_id }}</button>
              <span v-else class="muted">-</span>
            </td>
            <td>{{ row.count }}</td>
            <td>{{ row.fix_version || '-' }}</td>
            <td class="mono muted">
              <div>{{ fmtTs(row.first_ts) }}</div>
              <div>{{ fmtTs(row.latest_ts) }}</div>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="foot">
        <span class="muted">
          共 {{ total }} 个 cluster
          <template v-if="items[0]?.link">
            · 现行 link：{{ linkOffline(items[0].link.offline_status) }}
          </template>
        </span>
        <span v-if="total > pageSize">
          <button class="btn-ghost" type="button" :disabled="page <= 1" @click="doSearch(page - 1)">上一页</button>
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
.cards {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.card {
  flex: 1;
  min-width: 220px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-panel);
  padding: 10px 12px;
}

.card strong {
  font-size: 13px;
  color: var(--muted);
  display: block;
  margin-bottom: 8px;
}

.card.grow {
  flex: 2;
}

.kv {
  list-style: none;
  margin: 0;
  padding: 0;
}

.kv li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
  font-size: 13px;
}

.kv b {
  font-weight: 600;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  display: inline-block;
}

.tofix {
  font-size: 22px;
  font-weight: 600;
  margin: 4px 0;
}

.note {
  font-size: 12px;
}

.query {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.agent-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
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

.link-like {
  border: none;
  background: none;
  padding: 0;
  color: var(--brand);
  font-size: 12px;
  cursor: pointer;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

th {
  color: var(--muted);
  font-weight: 500;
  white-space: nowrap;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover {
  background: #fafbfc;
}

.err {
  max-width: 240px;
  word-break: break-all;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.short {
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.small {
  font-size: 12px;
}

.status {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.st-open, .st-assembled { background: #e8eaf0; color: #4b5563; }
.st-claim, .st-draft { background: #fdf1dc; color: #9a6b00; }
.st-fixed, .st-active { background: #e7f3e9; color: var(--ok); }
.st-inactive { background: #e8eaf0; color: #6b7280; }
.st-needs_review, .st-invalidated { background: var(--hl-red); color: var(--error); }

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
