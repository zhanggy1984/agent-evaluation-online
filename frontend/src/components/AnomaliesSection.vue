<script setup lang="ts">
// 异常列表（T-2.4）：anomalies 端点是实时事件列表（不做 rollup，rollup 丢 trace 身份）。
// 红显 = request 节点 status ∈ {error, timeout}；行点击下钻原 trace（复用详情页）。
import { agentDisplay } from '../composables/useAgents'
import { fmtDT } from '../format'
import type { AnomalyItem } from '../api/types'

defineProps<{ items: AnomalyItem[]; loading: boolean; sort: string }>()
const emit = defineEmits<{
  (e: 'open', row: { agent: string; traceId: string }): void
  (e: 'toggle-sort'): void
}>()

// null → '-'（不留 "- ms" 尾巴）
function durText(v: number | null): string {
  return v === null || v === undefined ? '-' : `${Math.round(v)} ms`
}

function toOpen(row: AnomalyItem): void {
  if (row.agent && row.trace_id) {
    emit('open', { agent: row.agent, traceId: row.trace_id })
  }
}

function errText(r: AnomalyItem): string {
  return r.error_type || r.error_msg || '-'
}

function isTo(r: AnomalyItem): boolean {
  return r.status === 'timeout'
}
</script>

<template>
  <div class="panel">
    <!-- 标题跟随排序口径：不写死「时间倒序」——否则点完排序标题就在撒谎 -->
    <p class="slim head">
      异常（request 错误/超时，{{ sort === 'duration' ? '按耗时降序' : '时间倒序' }}）
    </p>
    <p v-if="loading && items.length === 0" class="muted slim">加载中…</p>
    <p v-else-if="items.length === 0" class="muted slim">窗口内无异常（错误 = 0）</p>
    <table v-else>
      <thead>
        <tr>
          <th>时间</th>
          <th title="产生该事件的智能体名（good-question / contract-check / smart-procurement / customer-service）">agent</th>
          <th title="一次请求链路的唯一标识：同一 trace_id 的所有事件属同一次调用">trace_id</th>
          <th>接口</th>
          <th>状态</th>
          <th
            class="sortable" :class="{ on: sort === 'duration' }"
            title="点击按耗时降序（无耗时的行沉底）；再次点击恢复时间倒序"
            @click="emit('toggle-sort')"
          >耗时 <span class="caret">›</span></th>
          <th>错误</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(r, i) in items" :key="`${r.agent}#${r.trace_id}#${i}`"
          :class="{ clickable: r.agent && r.trace_id }" @click="toOpen(r)"
        >
          <td>{{ fmtDT(r.ts) }}</td>
          <td>{{ agentDisplay(r.agent) }}</td>
          <td class="mono">{{ r.trace_id }}</td>
          <td>{{ r.interface }}</td>
          <td><span class="st" :class="isTo(r) ? 'to' : 'err'">{{ r.status }}</span></td>
          <td class="num">{{ durText(r.duration_ms) }}</td>
          <td class="err">{{ errText(r) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* P1-6：可排序表头。默认无箭头、不喧哗；激活时才亮 —— 与 /interfaces 同一套观感。 */
th.sortable {
  cursor: pointer;
  user-select: none;
}

th.sortable .caret {
  display: inline-block;
  opacity: 0.35;
  transform: rotate(90deg); /* 默认朝下，表示"可排但未排" */
}

th.sortable.on {
  color: var(--fg);
}

th.sortable.on .caret {
  opacity: 1;
}

.head {
  margin: 0 0 8px;
  font-weight: 600;
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

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
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
</style>
