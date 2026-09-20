<script setup lang="ts">
// 接口面板（T-2.4）：单 body 双 filter agg 的消费端——请求级 / LLM 级双 tab。
// LLM 级接口行点击展开 model 明细（折叠态默认收起，防深表刷屏）。
import { computed, ref } from 'vue'

import { fmtInt, fmtMs, fmtPct } from '../format'
import type { LlmIfaceRow, MetricsInterfaces, ReqIfaceRow } from '../api/types'

const props = defineProps<{
  payload: MetricsInterfaces | null
  loading: boolean
  // P1-6：'' = 默认（按请求量降序）；'error' = 按错误数降序。
  // 排序在**后端**做（ES terms order 同时决定取哪 top50 桶），前端不重排。
  sort: string
}>()

const emit = defineEmits<{ (e: 'toggle-sort'): void }>()

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

    <!-- P1-6：排序改的是「取哪 50 个接口」而不只是顺序 —— 不写清楚会被读成「还是那批、
         只是重排」，进而把「没上榜」误当作「没出错」。 -->
    <p v-if="props.sort === 'error' && (reqRows.length > 0 || llmRows.length > 0)" class="muted slim hint">
      按错误数排序：每个 tab 只列出<strong>错误最多的 50 个接口</strong>（不是请求量最大的 50 个）—— 未上榜 ≠ 没出错。
    </p>

    <!-- P1-6：后端 terms size=50 是硬上限，超了会**静默少显示**（实测 7d 请求级 64 种只剩 50）。
         不写这行的话，「表里没有」会被读成「没有流量」——数字不假，但读者的结论假。 -->
    <p v-if="props.payload?.truncated" class="muted slim hint trunc-hint">
      请求级：窗口内共 {{ props.payload.iface_total }} 种接口，此处只显示{{
        props.sort === 'error' ? '错误最多' : '请求量最大' }}的 {{ reqRows.length }} 种 —— 未上榜 ≠ 没流量。
    </p>

    <p v-if="props.loading && !props.payload" class="muted slim">加载中…</p>

    <template v-else-if="tab === 'request'">
      <p v-if="reqRows.length === 0" class="muted slim">窗口内无 request 级事件</p>
      <table v-else>
        <thead>
          <tr>
            <th>接口</th>
            <th class="num">请求数</th>
            <th
              class="num sortable" :class="{ on: props.sort === 'error' }"
              title="点击切换：按错误数降序 / 按请求数降序"
              @click="emit('toggle-sort')"
            >错误{{ props.sort === 'error' ? ' ▾' : '' }}</th>
            <th class="num">超时</th>
            <th class="num" title="延迟分位数：P50 = 50% 的请求快于该值（中位数），P95/P99 同理">P50</th>
            <th class="num" title="延迟分位数：95% 的请求快于该值">P95</th>
            <th class="num" title="延迟分位数：99% 的请求快于该值">P99</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in reqRows" :key="r.interface" :class="{ red: redReq(r) }">
            <td>{{ r.interface }}</td>
            <td class="num">{{ fmtInt(r.total) }}</td>
            <td class="num" :class="{ red: r.error > 0 }">
              <!-- P1-11（2026-09-18）：错误数可点下钻到链路查询。
                   ⚠️ 落点条数**不保证**等于本页这个数字 —— 两者口径有两个独立差异：
                   ① 本页按**事件**计数（filter agg doc_count），链路列表按 **trace 去重**（折叠）；
                   ② 本页 error 只看 `node=request`（es.py:326），列表的 status 过滤不限节点。
                   实测 POST /api/chat/{id} 本页 7、列表 29（真机 2026-09-18，7d 窗）。
                   落点页顶部已有对应提示文案，不要删。error=0 时不给链接（点过去必然空）。 -->
              <router-link
                v-if="r.error > 0"
                class="err-link"
                :to="{ path: '/traces', query: { interface: r.interface, status: 'error' } }"
              >{{ r.error }}</router-link>
              <span v-else>0</span>
            </td>
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
            <th
              class="num sortable" :class="{ on: props.sort === 'error' }"
              title="点击切换：按失败数降序 / 按请求数降序"
              @click="emit('toggle-sort')"
            >失败{{ props.sort === 'error' ? ' ▾' : '' }}</th>
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
              <td class="muted">
                <!-- P2-29（2026-09-18）：箭头此前恒为 ▸，展开/收起两态无视觉区分。
                     旋转靠 .caret.on，不改文字（改了会破坏「点击展开」这句话的可读性）。 -->
                <span class="caret" :class="{ on: expanded === r.interface }">▸</span>
                {{ expanded === r.interface ? '收起' : `展开 ${r.models.length} 个模型` }}
              </td>
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

/* P1-6：排序表头（仅「错误」/「失败」两列，与后端 sort 白名单一一对应） */
th.sortable {
  cursor: pointer;
  user-select: none;
}

th.sortable:hover {
  color: var(--text);
}

th.sortable.on {
  color: var(--brand);
  font-weight: 600;
}

.hint {
  font-size: 12px;
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
  background: var(--hover-row);
}

tr.red td:first-child {
  box-shadow: inset 3px 0 0 var(--error);
}

/* P1-11：错误数下钻链接（仅 error>0 渲染；0 不留不可点的死样式） */
.err-link {
  color: var(--brand);
  text-decoration: underline;
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
  background: var(--bg);
}

table.inner th,
table.inner td {
  border-bottom: none;
  padding: 4px 8px;
  font-size: 12px;
}

tr.sub td {
  background: var(--bg);
  padding: 4px 8px 10px;
}

.caret {
  display: inline-block;
  transition: transform 0.15s;
}

.caret.on {
  transform: rotate(90deg);
}
</style>
