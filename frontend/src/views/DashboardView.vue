<script setup lang="ts">
// 指标看板（T-2.4，detail §8.4 四端点消费端）：
// - 筛选 {window, agent}，任一变化即重拉四端点；agent 空 = 全站。
// - 7d 走 rollup 读路径：source=realtime/mixed 或 fallback_hours 非空 → 顶部横幅回退实时口径。
// - 异常 / LLM 失败现场行点击下钻原 trace（复用详情页，不重复实现）。
// 二期物（L3 质量/弃留墙）整条隐藏不灰置，dashboard 只渲染 v1 功能。
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { logout } from '../api/auth'
import { ApiError, readStoredUser } from '../api/client'
import {
  metricsAnomalies,
  metricsInterfaces,
  metricsLlmFailures,
  metricsOverview,
} from '../api/metrics'
import type {
  MetricsAnomalies,
  MetricsInterfaces,
  MetricsLlmFailures,
  MetricsOverview,
} from '../api/types'
import AnomaliesSection from '../components/AnomaliesSection.vue'
import EmptyState from '../components/EmptyState.vue'
import InterfacesSection from '../components/InterfacesSection.vue'
import LlmFailuresSection from '../components/LlmFailuresSection.vue'
import MetricCards from '../components/MetricCards.vue'
import TimeSeriesChart from '../components/TimeSeriesChart.vue'
import { fmtAxis, fmtPct } from '../format'

const router = useRouter()
const user = readStoredUser()

const WINDOWS = [
  { v: '1h', label: '近 1 小时' },
  { v: '24h', label: '近 24 小时' },
  { v: '7d', label: '近 7 天' },
] as const

// 已接入的 canonical agent 列表（agent 轨真实接入随 T-2.5 扩展，空 = 全站）
const AGENTS = ['good-question', 'customer-service', 'contract-check', 'smart-procurement']

const window = ref<string>('1h')
const agent = ref<string>('') // '' = 全站
const loading = ref(false)
const errorMsg = ref('')
let seq = 0 // 竞态护栏：切筛选后只采纳最新一轮

const overview = ref<MetricsOverview | null>(null)
const interfaces = ref<MetricsInterfaces | null>(null)
const anomalies = ref<MetricsAnomalies | null>(null)
const llmFailures = ref<MetricsLlmFailures | null>(null)

// 线定义（颜色走 CSS var，经 chart 的 style 绑定才能解析）
const BRAND = 'var(--brand)'
const ERR = 'var(--error)'
const TO = 'var(--timeout)'

const qpsLines = [{ key: 'qps', label: 'QPS', color: BRAND }]
const rateLines = [
  { key: 'error_rate', label: '失败率', color: ERR },
  { key: 'timeout_rate', label: '超时率', color: TO },
]

function xFmt(ts: number): string {
  return fmtAxis(ts, window.value)
}

function yFmtRate(v: number): string {
  return fmtPct(v)
}

function yFmtQps(v: number): string {
  return v.toFixed(2)
}

const hasTraffic = computed(() => {
  const o = overview.value
  return !!o && (o.cards.total > 0 || o.series.some((p) => (p.count ?? 0) > 0))
})

const sourceLabel = computed(() => {
  const s = overview.value?.source
  if (s === 'rollup') return '小时聚合'
  if (s === 'mixed') return '混合'
  return '实时'
})

// 7d 顶部横幅：整窗或部分小时回退实时口径
const banner = computed(() => {
  if (window.value !== '7d' || !overview.value) return null
  const src = overview.value.source
  if (src === 'realtime') return '7d 无 rollup 覆盖，整窗按实时口径回算（聚合索引未生成或缺口）'
  if (src === 'mixed' && overview.value.fallback_hours.length > 0) {
    return `部分时段回退实时口径（${overview.value.fallback_hours.length} 个整点小时无 rollup 覆盖）`
  }
  return null
})

function emptyKind(): 'no_traffic' | 'no_rollup' {
  const realtime7d = window.value === '7d' && overview.value?.source === 'realtime'
  return realtime7d ? 'no_rollup' : 'no_traffic'
}

async function load(): Promise<void> {
  const my = ++seq
  loading.value = true
  errorMsg.value = ''
  const a = agent.value || null
  const w = window.value
  try {
    const [ov, itf, anm, llm] = await Promise.all([
      metricsOverview(a, w),
      metricsInterfaces(a, w),
      metricsAnomalies(a, w),
      metricsLlmFailures(a, w),
    ])
    if (my !== seq) return // 已被更新的请求取代
    overview.value = ov
    interfaces.value = itf
    anomalies.value = anm
    llmFailures.value = llm
  } catch (e) {
    if (my !== seq) return
    if (e instanceof ApiError) {
      errorMsg.value = `指标查询失败（${e.code}）：${e.message}`
    } else {
      throw e
    }
  } finally {
    if (my === seq) loading.value = false
  }
}

function openTrace(row: { agent: string; traceId: string }): void {
  void router.push({ name: 'trace-detail', params: { agent: row.agent, traceId: row.traceId } })
}

async function doLogout(): Promise<void> {
  await logout()
  void router.push({ name: 'login' })
}

watch([window, agent], () => void load())
onMounted(() => void load())

// 序列取每行可画字段：count 桶空时 qps 为 null → 断点，error_rate 同理。
// 显式标 Record 下标形状：chart 的 data prop 是 Record 数组，防 vue-tsc 严格索引报错。
type Row = Record<string, number | null>
const chartRows = computed<Row[]>(() =>
  (overview.value?.series ?? []).map((p): Row => ({
    ts: p.ts,
    qps: p.qps,
    error_rate: p.error_rate,
    timeout_rate: p.timeout_rate,
  })),
)
</script>

<template>
  <div>
    <header class="bar">
      <strong>obs 指标看板</strong>
      <span class="muted right">
        <router-link class="nav" :to="{ name: 'traces' }">链路查询</router-link>
        {{ user ? `${user.username}（${user.role}）` : '' }}
        <button class="btn-ghost" type="button" @click="doLogout">退出</button>
      </span>
    </header>

    <div class="panel ctrl">
      <div class="ctrl-row">
        <label class="muted lab">agent</label>
        <select v-model="agent" class="sel">
          <option value="">全站</option>
          <option v-for="a in AGENTS" :key="a" :value="a">{{ a }}</option>
        </select>
        <span class="win-group">
          <button
            v-for="w in WINDOWS" :key="w.v" type="button"
            class="win" :class="{ on: window === w.v }" @click="window = w.v"
          >{{ w.label }}</button>
        </span>
        <button class="btn ghost-inline" type="button" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
        <span v-if="overview" class="muted src">
          数据源：{{ sourceLabel }} · agent：{{ overview.agent ?? '全站' }}
        </span>
      </div>
      <p v-if="banner" class="warn">{{ banner }}</p>
    </div>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>

    <p v-if="loading && !overview" class="muted">加载中…</p>

    <!-- 查询失败且无旧数据：只显示错误，不再渲染"暂无流量"空态以免误导 -->
    <p v-else-if="errorMsg && !hasTraffic" class="muted">本次查询无可用数据，请按上方错误提示处理。</p>

    <EmptyState v-else-if="!hasTraffic" :kind="emptyKind()" />

    <template v-else>
      <section class="panel">
        <h2 class="sec">概览</h2>
        <MetricCards :cards="overview ? overview.cards : null" :loading="loading" />

        <div class="charts">
          <div class="chart-box">
            <p class="chart-title">QPS 趋势</p>
            <TimeSeriesChart
              :data="chartRows" :lines="qpsLines"
              :xFmt="xFmt" :yFmt="yFmtQps" :height="140"
            />
          </div>
          <div class="chart-box">
            <p class="chart-title">失败率 / 超时率</p>
            <TimeSeriesChart
              :data="chartRows" :lines="rateLines"
              :xFmt="xFmt" :yFmt="yFmtRate" :height="140"
            />
          </div>
        </div>
      </section>

      <h2 class="sec-plain">接口维度</h2>
      <InterfacesSection :payload="interfaces" :loading="loading" />

      <h2 class="sec-plain">异常与 LLM 失败现场</h2>
      <div class="grid2">
        <AnomaliesSection :items="anomalies ? anomalies.items : []" :loading="loading" @open="openTrace" />
        <LlmFailuresSection :items="llmFailures ? llmFailures.items : []" :loading="loading" @open="openTrace" />
      </div>
    </template>
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

.nav {
  font-size: 13px;
}

.ctrl {
  margin-bottom: 12px;
}

.ctrl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.lab {
  font-size: 13px;
}

.sel {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
}

.win-group {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}

.win {
  border: none;
  background: #fff;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--muted);
}

.win.on {
  background: var(--brand);
  color: #fff;
}

.ghost-inline {
  padding: 5px 12px;
  font-size: 13px;
  background: #fff;
  color: var(--brand);
  border: 1px solid var(--border);
  border-radius: 4px;
}

.src {
  font-size: 12px;
}

.warn {
  margin: 8px 0 0;
  padding: 7px 10px;
  background: #fef3e2;
  border: 1px solid #f4d5a8;
  color: var(--timeout);
  border-radius: 4px;
  font-size: 13px;
}

.sec {
  font-size: 15px;
  margin: 0 0 10px;
}

.sec-plain {
  font-size: 14px;
  margin: 16px 0 8px;
}

.charts {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.chart-box {
  flex: 1 1 420px;
  min-width: 320px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px 10px;
  background: #fafbfc;
}

.chart-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
}

.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

@media (max-width: 900px) {
  .grid2 {
    grid-template-columns: 1fr;
  }
}
</style>
