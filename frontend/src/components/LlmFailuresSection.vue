<script setup lang="ts">
// LLM 失败现场（T-2.4）：请求成功(request ok)但 LLM 节点失败的兜底/降级事件，
// 不计入接口失败率（口径归 llm-failures 下钻）；行点击下钻原 trace 看现场。
import { fmtDT } from '../format'
import type { LlmFailureItem } from '../api/types'

defineProps<{ items: LlmFailureItem[]; loading: boolean }>()
const emit = defineEmits<{ (e: 'open', row: { agent: string; traceId: string }): void }>()

function toOpen(r: LlmFailureItem): void {
  if (r.agent && r.trace_id) emit('open', { agent: r.agent, traceId: r.trace_id })
}

function errText(r: LlmFailureItem): string {
  return r.llm_error_type || r.llm_error_msg || '-'
}

function stCls(r: LlmFailureItem): string {
  if (r.llm_node_status === 'timeout') return 'to'
  return r.llm_node_status === 'ok' ? 'ok' : 'err'
}

// request 不在窗内/缺失 → '-'（接口不猜测兜底状态）
function reqStatus(r: LlmFailureItem): string {
  return r.request_status ?? '-'
}
</script>

<template>
  <div class="panel">
    <p class="slim head">LLM 失败现场（请求 ok + LLM 节点失败，时间倒序）</p>
    <p class="muted slim note">
      兜底/降级现场不计入接口失败率（v1 不回流、L3 二期接入）；点击行下钻原 trace。
    </p>
    <p v-if="loading && items.length === 0" class="muted slim">加载中…</p>
    <p v-else-if="items.length === 0" class="muted slim">窗口内无 LLM 失败现场</p>
    <table v-else>
      <thead>
        <tr>
          <th>时间</th>
          <th>agent</th>
          <th>trace_id</th>
          <th>接口</th>
          <th>请求状态</th>
          <th>LLM 节点</th>
          <th>模型</th>
          <th>LLM 错误</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(r, i) in items" :key="`${r.agent}#${r.trace_id}#${i}`"
          :class="{ clickable: r.agent && r.trace_id }" @click="toOpen(r)"
        >
          <td>{{ fmtDT(r.ts) }}</td>
          <td>{{ r.agent }}</td>
          <td class="mono">{{ r.trace_id }}</td>
          <td>{{ r.interface }}</td>
          <td>{{ reqStatus(r) }}</td>
          <td><span class="st" :class="stCls(r)">{{ r.llm_node_status }}</span></td>
          <td class="mono sm">{{ r.model }}</td>
          <td class="err">{{ errText(r) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.head {
  margin: 0 0 4px;
  font-weight: 600;
}

.note {
  margin: 0 0 8px;
  font-size: 12px;
}

.slim {
  margin: 6px 0;
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
  font-size: 12px;
}

tr.clickable {
  cursor: pointer;
}

tr.clickable:hover {
  background: #fafbfc;
}

.st {
  display: inline-block;
  padding: 0 7px;
  border-radius: 3px;
  font-size: 12px;
}

.st.err {
  color: var(--error);
  background: var(--hl-red);
}

.st.to {
  color: var(--timeout);
  background: #fef3e2;
}

.st.ok {
  color: var(--ok);
  background: #e9f6ec;
}

.err {
  color: var(--error);
  word-break: break-all;
  max-width: 280px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
  max-width: 260px;
}

.sm {
  font-size: 12px;
}
</style>
