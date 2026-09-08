<script setup lang="ts">
// 链路查询页：trace_id / keyword 可任一（都空 = 近 7d 全部命中），agent 过滤。
// 检索走后端默认时间窗（keyword_search_days=7）与 ≤200 上限；红显 = status∈{error,timeout}。
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { logout } from '../api/auth'
import { ApiError, readStoredUser } from '../api/client'
import { listTraces } from '../api/traces'
import type { TraceListItem } from '../api/types'

const router = useRouter()

const queryForm = ref({ trace_id: '', keyword: '', agent: '' })
const loading = ref(false)
const errorMsg = ref('')
const items = ref<TraceListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const maxPages = Math.ceil(200 / pageSize) // §14.4 深翻页上限 200 → 前端最多 10 页

const user = readStoredUser()

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

async function doSearch(p = 1): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const q = {
      trace_id: queryForm.value.trace_id.trim() || undefined,
      keyword: queryForm.value.keyword.trim() || undefined,
      agent: queryForm.value.agent.trim() || undefined,
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

function rowKey(row: TraceListItem): string {
  // 折叠列表一行 = (agent, trace_id) 唯一；字段可空 → 拼接兜底成稳定字符串 key
  return `${row.agent ?? ''}#${row.trace_id ?? ''}`
}

function toDetail(row: TraceListItem): void {
  if (row.agent && row.trace_id) {
    void router.push({ name: 'trace-detail', params: { agent: row.agent, traceId: row.trace_id } })
  }
}

async function doLogout(): Promise<void> {
  // 先 revoke 再清本地再跳转：跳早了守卫仍见 token 会把 /login 弹回 /traces
  await logout()
  void router.push({ name: 'login' })
}

onMounted(() => void doSearch(1))
</script>

<template>
  <div>
    <header class="bar">
      <strong>obs 链路查询</strong>
      <span class="muted right">
        {{ user ? `${user.username}（${user.role}）` : '' }}
        <button class="btn-ghost" type="button" @click="doLogout">退出</button>
      </span>
    </header>

    <form class="panel query" @submit.prevent="resetAndSearch">
      <input v-model="queryForm.trace_id" placeholder="trace_id（精确）" />
      <input v-model="queryForm.keyword" placeholder="错误关键字" />
      <input v-model="queryForm.agent" placeholder="agent" />
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? '查询中…' : '查询' }}
      </button>
    </form>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>

    <div class="panel list">
      <p class="muted" v-if="!loading && items.length === 0">无命中 trace（近 7 天检索窗，可缩小 trace_id / keyword 重试）</p>
      <table v-else>
        <thead>
          <tr>
            <th>时间</th>
            <th>agent</th>
            <th>trace_id</th>
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
            <td>{{ row.agent }}</td>
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
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.right {
  display: inline-flex;
  gap: 10px;
  align-items: center;
}

.query {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.query input {
  flex: 1;
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
  background: #fafbfc;
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
