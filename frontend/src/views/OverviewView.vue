<script setup lang="ts">
// 总览页（IA 重构后一级菜单"总览"，落点 /dashboard，detail §9.1 v1.13）：
// - 只拉 metrics/overview 单端点；筛选 {agent, window} 由 MetricFilterBar 读写共享 store。
// - 7d 走 rollup 读路径：source=rollup/mixed/realtime + fallback_hours → 数据源徽标/回退横幅。
// - Q7 决策：本页 60s 自动刷新（对齐后端 O-1 60s 缓存），其余指标页手动刷新。
// - 双趋势图 + 概览卡 + no_traffic/no_rollup 空态保留。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ApiError } from '../api/client'
import { metricsOverview } from '../api/metrics'
import type { MetricsOverview } from '../api/types'
import EmptyState from '../components/EmptyState.vue'
import MetricCards from '../components/MetricCards.vue'
import MetricFilterBar from '../components/MetricFilterBar.vue'
import TimeSeriesChart from '../components/TimeSeriesChart.vue'
import { useMetricFilter } from '../composables/useMetricFilter'
import { fmtAxis, fmtPct } from '../format'

const { filter } = useMetricFilter()

const AUTO_REFRESH_MS = 60_000 // Q7：对齐后端 O-1 60s 缓存

const overview = ref<MetricsOverview | null>(null)
const loading = ref(false)
const errorMsg = ref('')
let seq = 0 // 竞态护栏：筛选/自动刷新切换后只采纳最新一轮

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
  return fmtAxis(ts, filter.window)
}

function yFmtRate(v: number): string {
  return fmtPct(v)
}

function yFmtQps(v: number): string {
  return v.toFixed(2)
}

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
  if (filter.window !== '7d' || !overview.value) return null
  const src = overview.value.source
  if (src === 'realtime') return '7d 无 rollup 覆盖，整窗按实时口径回算（聚合索引未生成或缺口）'
  if (src === 'mixed' && overview.value.fallback_hours.length > 0) {
    return `部分时段回退实时口径（${overview.value.fallback_hours.length} 个整点小时无 rollup 覆盖）`
  }
  return null
})

function emptyKind(): 'no_traffic' | 'no_rollup' {
  const realtime7d = filter.window === '7d' && overview.value?.source === 'realtime'
  return realtime7d ? 'no_rollup' : 'no_traffic'
}

async function load(): Promise<void> {
  const my = ++seq
  loading.value = true
  errorMsg.value = ''
  const a = filter.agent || null
  const w = filter.window
  try {
    const ov = await metricsOverview(a, w)
    if (my !== seq) return // 已被更新的请求取代
    overview.value = ov
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

// Q7：总览页 60s 自动刷新（页面卸载即停）；在飞请求时跳过本轮（seq 护栏防陈旧覆盖）
let timer: number | undefined
function startAuto(): void {
  stopAuto()
  timer = window.setInterval(() => {
    if (!loading.value) void load()
  }, AUTO_REFRESH_MS)
}
function stopAuto(): void {
  if (timer !== undefined) window.clearInterval(timer)
  timer = undefined
}

// 筛选变化：清旧数据防跨范围误读（空态标题按新窗判断），再重拉
watch(
  () => [filter.agent, filter.window] as const,
  () => {
    overview.value = null
    void load()
  },
)

onMounted(() => {
  void load()
  startAuto()
})
onUnmounted(stopAuto)
</script>

<template>
  <div>
    <MetricFilterBar :loading="loading" @refresh="load" />

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading && !overview" class="muted">加载中…</p>

    <!-- 查询失败且无旧数据：只显示错误，不再渲染"暂无流量"空态以免误导 -->
    <p v-else-if="errorMsg && !hasTraffic" class="muted">本次查询无可用数据，请按上方错误提示处理。</p>

    <EmptyState v-else-if="!hasTraffic" :kind="emptyKind()" />

    <template v-else>
      <section class="panel">
        <div class="sec-row">
          <h2 class="sec">概览</h2>
          <span v-if="overview" class="muted src">
            数据源：{{ sourceLabel }} · agent：{{ overview.agent ?? '全站' }} · 窗口 {{ filter.window }}
          </span>
        </div>
        <p v-if="banner" class="warn">{{ banner }}</p>
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
        <p class="muted auto">每 60s 自动刷新（对齐后端缓存）</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.sec-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}

.sec {
  font-size: 15px;
  margin: 0;
}

.src {
  font-size: 12px;
}

.warn {
  margin: 0 0 10px;
  padding: 7px 10px;
  background: #fef3e2;
  border: 1px solid #f4d5a8;
  color: var(--timeout);
  border-radius: 4px;
  font-size: 13px;
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

.auto {
  margin: 10px 0 0;
  font-size: 12px;
}
</style>
