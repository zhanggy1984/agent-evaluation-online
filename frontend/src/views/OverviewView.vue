<script setup lang="ts">
// 总览页（IA 重构后一级菜单"总览"，落点 /dashboard，detail §9.1 v1.13）：
// - 只拉 metrics/overview 单端点；筛选 {agent, window} 由 MetricFilterBar 读写共享 store。
// - 7d 走 rollup 读路径：source=rollup/mixed/realtime + fallback_hours → 数据源徽标/回退横幅。
// - v1.14：45s 自动刷新（< 后端 60s 缓存 TTL 且非整约 → 每 tick 命中缓存，后端实查约减半）
//   仅在页面可见且在飞请求时进行；切回前台 >15s 陈旧补一轮；后台暂停。
// - 双趋势图 + 概览卡 + no_traffic/no_rollup 空态保留。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ApiError } from '../api/client'
import { metricsOverview } from '../api/metrics'
import type { MetricsOverview } from '../api/types'
import EmptyState from '../components/EmptyState.vue'
import MetricCards from '../components/MetricCards.vue'
import MetricFilterBar from '../components/MetricFilterBar.vue'
import { agentDisplay } from '../composables/useAgents'
import TimeSeriesChart from '../components/TimeSeriesChart.vue'
import { useMetricFilter } from '../composables/useMetricFilter'
import { fmtAxis, fmtPct } from '../format'

const { filter } = useMetricFilter()

// 空态动作（P1-16）：清除筛选 = 回到默认窗口 + 全站（与 useMetricFilter 的默认值一致）
function resetFilter(): void {
  filter.window = '24h'
  filter.agent = ''
}

// 45s：< 后端 O-1 60s TTL 且非其整约数 → 每 tick 落在缓存存活期多命中一次；选 45 不为 60 的
// 约数，避免 30s 等仍会周期性对齐后端失效瞬间。TTL=0（禁缓存）时接受每分钟实查全量（运维权衡）。
const AUTO_REFRESH_MS = 45_000

const overview = ref<MetricsOverview | null>(null)
const loading = ref(false)
const errorMsg = ref('')
let seq = 0 // 竞态护栏：筛选/自动刷新切换后只采纳最新一轮
let lastLoadTs = 0 // 最近一次成功装载时刻（可见性补轮基准）

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

// 7d 顶部横幅「部分时段按实时数据计算（N 个小时没有聚合数据）」2026-09-20 整体移除，两因：
// ① 措辞与实现不符：`fallback_hours` 的那几个小时**不是「用实时数据补上了」，是根本没进分位**
//    （metrics.py:393-398 —— 只 merge rollup 覆盖小时的 sketch；计数/率/序列本来就恒走实时整窗）。
//    读起来像「数据完整性的保证」，事实是「分位覆盖率不足」，方向相反。
// ② 同页 rollupNote 已用准确措辞说了同一件事（168−130=38，是同一个数的两面），
//    且它明说「哪些字段受影响」——banner 只是同一事实的第二遍渲染，措辞还更差。
// 保留 rollupNote 即信息不丢；不做「降级成普通提示」是避免同页说两遍。

// v1.14 分位标注：7d 有 rollup 覆盖时，分位与计数是不同样本（§4.4 口径）——分位仅覆盖小时、
// 计数/序列实时全窗。UI 明示避免"卡与图对不上"的误读（挑战点 1.2 落字）。
// v1.15（批 40）只改**归因方向**，口径一字未动：原括注写「汇总只到上一个整点，之后的流量
// 不计入分位」——它只解释了**尾部**，而 `covered_hours` 与窗口长度的差 98% 来自**头部**
// （rollup 起点之前的时段）。实测：7d 窗内 request 事件 1396，落在 rollup 覆盖期内的仅 28 条
// ⇒ 未计入的 1368 条全在头部。旧措辞会让读者以为"只差最后一个小时"，从而反复追问这个数
// 是怎么来的。改为不指定方向的「本窗内未汇总的时段」，在成长中／满覆盖两种状态下都成立。
const rollupNote = computed(() => {
  const o = overview.value
  if (filter.window !== '7d' || !o) return null
  if (o.source !== 'rollup' && o.source !== 'mixed') return null
  return (
    `延迟分位(P50/P95/P99) 基于 ${o.covered_hours} 个小时的汇总数据` +
    '（本窗内未汇总的时段与进行中的整点不计入分位）；总数/失败率/序列按实时数据统计'
  )
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
    lastLoadTs = Date.now()
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

// 自动刷新（页面卸载即停）：后台（document.hidden）跳过、在飞请求跳过（seq 护栏防陈旧覆盖）
let timer: number | undefined
function startAuto(): void {
  stopAuto()
  timer = window.setInterval(() => {
    if (document.hidden || loading.value) return
    void load()
  }, AUTO_REFRESH_MS)
}
function stopAuto(): void {
  if (timer !== undefined) window.clearInterval(timer)
  timer = undefined
}

// 切回前台且数据超 15s 陈旧 → 立即补一轮（后台期间 tick 被跳，避免回前台看旧数等下一个 45s）
function onVisibility(): void {
  if (!document.hidden && !loading.value && Date.now() - lastLoadTs > 15_000) {
    void load()
  }
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
  document.addEventListener('visibilitychange', onVisibility)
})
onUnmounted(() => {
  stopAuto()
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <div>
    <MetricFilterBar :loading="loading" @refresh="load" />

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading && !overview" class="muted">加载中…</p>

    <!-- 查询失败且无旧数据：只显示错误，不再渲染"暂无流量"空态以免误导 -->
    <p v-else-if="errorMsg && !hasTraffic" class="muted">本次查询无可用数据，请按上方错误提示处理。</p>

    <EmptyState v-else-if="!hasTraffic" :kind="emptyKind()">
      <template #actions>
        <button
          v-if="filter.window !== '7d'"
          class="btn"
          type="button"
          @click="filter.window = '7d'"
        >改为近 7 天</button>
        <button class="btn-ghost" type="button" @click="resetFilter">清除筛选</button>
      </template>
    </EmptyState>

    <template v-else>
      <section class="panel">
        <div class="sec-row">
          <h2 class="sec">概览</h2>
          <span v-if="overview" class="muted src">
            数据源：{{ sourceLabel }} · agent：{{ overview.agent ? agentDisplay(overview.agent) : '全站' }} · 窗口 {{ filter.window }}
          </span>
        </div>
        <p v-if="rollupNote" class="muted note">{{ rollupNote }}</p>
        <MetricCards :cards="overview ? overview.cards : null" :loading="loading" />

        <div class="charts">
          <div class="chart-box">
            <p class="chart-title">QPS 趋势</p>
            <TimeSeriesChart
              :data="chartRows" :lines="qpsLines"
              :xFmt="xFmt" :yFmt="yFmtQps" :height="170"
            />
          </div>
          <div class="chart-box">
            <p class="chart-title">失败率 / 超时率</p>
            <TimeSeriesChart
              :data="chartRows" :lines="rateLines"
              :xFmt="xFmt" :yFmt="yFmtRate" :height="170"
            />
          </div>
        </div>
        <p class="muted auto">自动刷新 · 后台自动暂停</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.sec-row {
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}

/* 小节标题：左侧 3px 竖条 + 字距。竖条是全站通用的「这里是读数区起点」记号，
   与卡片左边条同一套语汇（颜色=状态），不额外引入图形元素。 */
.sec {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.03em;
  margin: 0;
  padding-left: 8px;
  border-left: 3px solid var(--brand);
  line-height: 1.2;
}

.src {
  font-size: 12px;
}

.charts {
  display: flex;
  gap: var(--sp-4);
  margin-top: var(--sp-5);
  flex-wrap: wrap;
}

/* 图表容器：与卡片同样用 --bg 凹槽（白面板上的内嵌区），全页内嵌区一个语汇。 */
.chart-box {
  flex: 1 1 420px;
  min-width: 320px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--sp-3) var(--sp-4) var(--sp-4);
  background: var(--bg);
}

.chart-title {
  margin: 0 0 var(--sp-2);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--muted);
}

.auto {
  margin: 10px 0 0;
  font-size: 12px;
}

.note {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.6;
}
</style>
