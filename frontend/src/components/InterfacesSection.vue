<script setup lang="ts">
// 接口面板（T-2.4）：单 body 双 filter agg 的消费端——请求级 / LLM 级双 tab。
// LLM 级接口行点击展开 model 明细（折叠态默认收起，防深表刷屏）。
import { computed, ref } from 'vue'

import { fmtInt, fmtMs, fmtPct } from '../format'
import type { LlmIfaceRow, MetricsInterfaces, ReqIfaceRow } from '../api/types'

const props = defineProps<{ payload: MetricsInterfaces | null; loading: boolean }>()

type Tab = 'request' | 'llm'
const tab = ref<Tab>('request')
const expanded = ref<string | null>(null) // 展开中的 llm 接口名（null = 全收起）

const reqRows = computed(() => props.payload?.request ?? [])
const llmRows = computed(() => props.payload?.llm ?? [])

function redReq(r: ReqIfaceRow): boolean {
  return r.error > 0 || r.timeout > 0
}

function toggle(key: string): void {
  expanded.value = expanded.value === key ? null : key
}

function llmRate(r: LlmIfaceRow): string {
  return fmtPct(r.llm_failure_rate)
}

function fmtTok(v: number): string {
  return fmtInt(v)
}
</script>

<template>
  <div class="panel">
    <div class="tabs">
      <button
        type="button" :class="{ on: tab === 'request' }"
        @click="tab = 'request'"
      >请求级接口（{{ reqRows.length }}）</button>
      <button
        type="button" :class="{ on: tab === 'llm' }"
        @click="tab = 'llm'"
      >LLM 级接口（{{ llmRows.length }}）</button>
    </div>

    <p v-if="props.loading && !props.payload" class="muted slim">加载中…</p>

    <template v-else-if="tab === 'request'">
      <p v-if="reqRows.length === 0" class="muted slim">窗口内无 request 级事件</p>
      <table v-else>
        <thead>
          <tr>
            <th>接口</th>
            <th class="num">请求数</th>
            <th class="num">错误</th>
            <th class="num">超时</th>
            <th class="num">P50</th>
            <th class="num">P95</th>
            <th class="num">P99</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in reqRows" :key="r.interface" :class="{ red: redReq(r) }">
            <td>{{ r.interface }}</td>
            <td class="num">{{ fmtInt(r.total) }}</td>
            <td class="num">{{ r.error }}</td>
            <td class="num">{{ r.timeout }}</td>
            <td class="num">{{ fmtMs(r.p50) }}</td>
            <td class="num">{{ fmtMs(r.p95) }}</td>
            <td class="num">{{ fmtMs(r.p99) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="muted slim unit">延迟单位 ms；红显 = 该接口含错误/超时</p>
    </template>

    <template v-else>
      <p v-if="llmRows.length === 0" class="muted slim">窗口内无 LLM 级事件</p>
      <table v-else class="llm">
        <thead>
          <tr>
            <th>接口</th>
            <th class="num">请求数</th>
            <th class="num">失败</th>
            <th class="num">LLM 失败率</th>
            <th>模型（点击展开）</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="r in llmRows" :key="r.interface">
            <tr
              class="iface" :class="{ on: expanded === r.interface }"
              @click="toggle(r.interface)"
            >
              <td>{{ r.interface }}</td>
              <td class="num">{{ fmtInt(r.total) }}</td>
              <td class="num" :class="{ red: r.error > 0 }">{{ r.error }}</td>
              <td class="num">{{ llmRate(r) }}</td>
              <td class="muted">▸ {{ expanded === r.interface ? '收起' : `展开 ${r.models.length} 个模型` }}</td>
            </tr>
            <tr v-if="expanded === r.interface" class="sub">
              <td colspan="5">
                <table class="inner">
                  <thead>
                    <tr>
                      <th>模型</th>
                      <th class="num">调用数</th>
                      <th class="num">错误</th>
                      <th class="num">输入 tokens</th>
                      <th class="num">输出 tokens</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="m in r.models" :key="m.model">
                      <td class="mono">{{ m.model }}</td>
                      <td class="num">{{ fmtInt(m.total) }}</td>
                      <td class="num" :class="{ red: m.error > 0 }">{{ m.error }}</td>
                      <td class="num">{{ fmtTok(m.prompt_tokens) }}</td>
                      <td class="num">{{ fmtTok(m.completion_tokens) }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-if="r.models.length === 0" class="muted slim">该接口无 model 分组样本</p>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p class="muted slim unit">
        LLM 失败率 = (error + timeout) / 调用数；接口行点击展开 model 明细（tokens 累计自 usage.*）
      </p>
    </template>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.tabs button {
  border: none;
  background: none;
  padding: 7px 14px;
  font-size: 13px;
  color: var(--muted);
  border-bottom: 2px solid transparent;
}

.tabs button.on {
  color: var(--brand);
  border-bottom-color: var(--brand);
  font-weight: 600;
}

.slim {
  margin: 8px 0;
}

.unit {
  font-size: 12px;
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

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

tr.iface {
  cursor: pointer;
}

tr.iface:hover {
  background: #fafbfc;
}

tr.red td:first-child {
  box-shadow: inset 3px 0 0 var(--error);
}

td.red {
  color: var(--error);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
  max-width: 320px;
}

table.inner {
  margin: 4px 0;
  background: #fafbfc;
}

table.inner th,
table.inner td {
  border-bottom: none;
  padding: 4px 8px;
  font-size: 12px;
}

tr.sub td {
  background: #fafbfc;
  padding: 4px 8px 10px;
}
</style>
