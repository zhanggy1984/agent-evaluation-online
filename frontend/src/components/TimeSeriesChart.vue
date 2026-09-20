<script setup lang="ts">
// 极简 SVG 时序折线（不引 ECharts/dataviz，T-2.4）：props 抽象线定义 + CSS var 颜色。
// 每条线取 data 行内对应 key（值 null 视为断点不连线）；hover 显示最近点数值浮层。
// 模板内一律不写 TS 语法（as/非空断言）——取值换算全收在 script，组件内复用。
import { computed, ref } from 'vue'

// 单条线的定义：key = data 行内取值字段，label = 图例名，color = 描边色（CSS var 或 hex）
interface SeriesLine {
  key: string
  label: string
  color: string
}

const props = defineProps<{
  data: Array<Record<string, number | null>>
  lines: SeriesLine[]
  xFmt: (ts: number) => string
  yFmt: (v: number) => string
  height?: number
}>()

const W = 720
const PAD_L = 46
const PAD_R = 12
const PAD_T = 10
const PAD_B = 24

const H = computed(() => props.height ?? 200)
const hover = ref<number | null>(null) // hover 的 row 下标

const rows = computed(() => props.data)
const innerW = W - PAD_L - PAD_R
const innerH = computed(() => H.value - PAD_T - PAD_B)

function numAt(i: number, key: string): number | null {
  const row = rows.value[i]
  if (!row) return null
  const v = row[key]
  return typeof v === 'number' ? v : null
}

const yDomain = computed(() => {
  let min = Infinity
  let max = -Infinity
  for (const r of rows.value) {
    for (const l of props.lines) {
      const v = numAt(rows.value.indexOf(r), l.key)
      if (v !== null) {
        if (v < min) min = v
        if (v > max) max = v
      }
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 }
  if (max === min) max = min + 1 // 全相等（含全 0）保高差免除零
  return { min, max }
})

function xAt(i: number): number {
  if (rows.value.length <= 1) return PAD_L + innerW / 2
  return PAD_L + (i * innerW) / (rows.value.length - 1)
}

function yAt(v: number): number {
  const { min, max } = yDomain.value
  return PAD_T + ((max - v) / (max - min)) * innerH.value
}

function linePath(l: SeriesLine): string {
  const segs: string[] = []
  let cur: string[] = []
  for (let i = 0; i < rows.value.length; i++) {
    const v = numAt(i, l.key)
    if (v !== null) {
      const cmd = cur.length === 0 ? 'M' : 'L'
      cur.push(`${cmd}${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`)
    } else if (cur.length) {
      segs.push(cur.join(' '))
      cur = []
    }
  }
  if (cur.length) segs.push(cur.join(' '))
  return segs.join(' ')
}

// 孤立点采集（2026-09-20）：**长度恰好为 1 的连续非空段**在 linePath 里只产出 "M x y"，
// 而 SVG 中只有 moveto、没有 lineto 的路径**什么都不画**（fill 又是 none）⇒
// 该点有真实读数却彻底不可见。
// 实测（/dashboard 7d, agent=contract-check）：error_rate 的段长分布是 [1,3,1,2,2,1]，
// 6 段里 3 段长度为 1 —— count 2 / 68 / 15 三个桶的读数全丢，其中 count=68 那次
// 失败率 1.47% 是个不该消失的点。此处把它们单独画成实心圆。
// ⚠️ 只补"点可见"，**不跨空桶连线** —— 空桶 = 无流量 = 算不出率，断开是对的语义。
const isolatedDots = computed(() => {
  const out: { id: string; x: number; y: number; color: string }[] = []
  const n = rows.value.length
  for (const l of props.lines) {
    let i = 0
    while (i < n) {
      const v = numAt(i, l.key)
      if (v === null) {
        i++
        continue
      }
      let j = i
      while (j + 1 < n && numAt(j + 1, l.key) !== null) j++
      if (j === i) out.push({ id: `${l.key}-${i}`, x: xAt(i), y: yAt(v), color: l.color })
      i = j + 1
    }
  }
  return out
})

// x 轴刻度：首尾必在、中间等分，最多 7 个（P2-23 主因）。
// 旧实现是「按 step 走网格 + 无条件补 n-1」，补位与末位网格点只隔几桶时两个标签会重叠
// （n=123 时末两刻度仅隔 2 桶，实测压在一起 11px）。等分生成让间距恒为 (n-1)/(count-1)，
// 从根上不存在「补位贴脸」；代价是刻度不再落在 step 的整数倍上（对读图无影响）。
const ticks = computed(() => {
  const n = rows.value.length
  if (!n) return [] as { i: number; text: string }[]
  const count = Math.min(7, n)
  const idx: number[] = []
  for (let k = 0; k < count; k++) {
    idx.push(count === 1 ? 0 : Math.round((k * (n - 1)) / (count - 1)))
  }
  // 标签去重（P2-23 次因）：7d 的 MM-DD 粒度粗于 1 小时桶，等分后相邻刻度仍可能同日
  // ⇒ 连续重复只保留第一个；被跳过者整个条目都不产出，即**该处不渲染任何东西**。
  // （x 轴本来就只有刻度文字、没有网格线，所以「少一个刻度」不会让任何线错位。）
  const out: { i: number; text: string }[] = []
  let prev = ''
  for (const i of [...new Set(idx)]) {
    const t = props.xFmt(rowTs(i))
    if (t === prev) continue
    out.push({ i, text: t })
    prev = t
  }
  return out
})

const gridVals = computed(() => {
  const { min, max } = yDomain.value
  return [0, 1, 2, 3, 4].map((i) => min + ((max - min) * i) / 4)
})

// y 轴标签（2026-09-20）：此前**只标首尾两个值**（模板里的三元判断），中间三条网格线
// 是无标签的装饰线 —— 画了线却读不出数，线越多越像"有刻度"，实际只能读两端。
// 现改为五条全标；并沿用 x 轴那套**相邻同文案只留第一个**的去重：极端量程下
// yFmt 可能把相邻两个值格式化成同一串（失败率量程极小时两位小数会撞），
// 那属于"这个刻度太小、量不出来"，不该硬渲染成两个一样的数。
const yLabels = computed(() => {
  const out: { i: number; y: number; text: string }[] = []
  let prev = ''
  gridVals.value.forEach((gv, i) => {
    const text = props.yFmt(gv)
    if (text === prev) return
    out.push({ i, y: yAt(gv) + 3, text })
    prev = text
  })
  return out
})

function nearestX(px: number): number {
  if (rows.value.length <= 1) return 0
  const raw = (px - PAD_L) / (innerW / (rows.value.length - 1))
  return Math.max(0, Math.min(rows.value.length - 1, Math.round(raw)))
}

// 模板内不写 TS 语法（as/非空断言）——取值收进这些帮手
function rowTs(i: number): number {
  const v = rows.value[i]?.ts
  return typeof v === 'number' ? v : 0
}

function guideX(): number {
  return hover.value === null ? 0 : xAt(hover.value)
}

function tipLeft(): string {
  return hover.value === null ? '0%' : `${(xAt(hover.value) / W) * 100}%`
}

function onMove(ev: MouseEvent): void {
  const el = ev.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const ratio = W / rect.width // viewBox 拉伸校正 → 内容坐标
  hover.value = nearestX((ev.clientX - rect.left) * ratio)
}

const tipRows = computed(() => {
  const i = hover.value
  if (i === null || !rows.value[i]) return null
  return {
    label: props.xFmt(rows.value[i].ts as number),
    vals: props.lines
      .filter((l) => numAt(i, l.key) !== null)
      .map((l) => ({ label: l.label, color: l.color, text: props.yFmt(numAt(i, l.key) as number) })),
  }
})

const hoverDots = computed(() => {
  const i = hover.value
  if (i === null || !rows.value[i]) return [] as { x: number; y: number; color: string }[]
  const out: { x: number; y: number; color: string }[] = []
  for (const l of props.lines) {
    const v = numAt(i, l.key)
    if (v !== null) out.push({ x: xAt(i), y: yAt(v), color: l.color })
  }
  return out
})
</script>

<template>
  <div v-if="rows.length" class="chart" @mousemove="onMove" @mouseleave="hover = null">
    <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none">
      <g v-for="(gv, i) in gridVals" :key="`g${i}`">
        <line :x1="PAD_L" :y1="yAt(gv)" :x2="W - PAD_R" :y2="yAt(gv)" class="grid" />
      </g>
      <text
        v-for="l in yLabels" :key="`y${l.i}`"
        :x="PAD_L - 4" :y="l.y" text-anchor="end" class="axis"
      >{{ l.text }}</text>
      <path
        v-for="l in lines" :key="l.key" :d="linePath(l)"
        :style="{ stroke: l.color }" fill="none" stroke-width="2" stroke-linejoin="round"
      />
      <circle
        v-for="d in isolatedDots" :key="`iso-${d.id}`"
        :cx="d.x" :cy="d.y" r="3" :style="{ fill: d.color }"
      />
      <template v-if="hover !== null">
        <line :x1="guideX()" :x2="guideX()" :y1="PAD_T" :y2="H - PAD_B" class="guide" />
        <circle
          v-for="(d, k) in hoverDots" :key="`d${k}`"
          :cx="d.x" :cy="d.y" r="3.5" :style="{ fill: d.color }"
        />
      </template>
      <text
        v-for="(t, k) in ticks" :key="`t${k}`"
        :x="xAt(t.i)" :y="H - 6" text-anchor="middle" class="axis"
      >{{ t.text }}</text>
    </svg>

    <div v-if="tipRows" class="tip" :style="{ left: tipLeft() }">
      <div class="tip-ts">{{ tipRows.label }}</div>
      <div v-for="(v, i) in tipRows.vals" :key="i" class="tip-row">
        <i class="dot" :style="{ background: v.color }" />
        <span>{{ v.label }}</span>
        <b>{{ v.text }}</b>
      </div>
    </div>

    <div class="legend">
      <span v-for="l in lines" :key="l.key" class="legend-item">
        <i class="dot" :style="{ background: l.color }" />{{ l.label }}
      </span>
    </div>
  </div>
  <p v-else class="muted empty">该时段无时序样本</p>
</template>

<style scoped>
.chart {
  position: relative;
}

.chart svg {
  width: 100%;
  height: auto;
  display: block;
}

/* 网格改实线细线（原为 2/3 点线）：点线在浅底上读起来像「没画完」，
   实线细网格才是仪表刻度盘的语汇。颜色仍取 --border，不喧宾夺主。 */
.grid {
  stroke: var(--border);
  stroke-width: 1;
}

/* 十字准星保留虚线：它跟网格是两种东西，虚线才能和常驻网格区分开。 */
.guide {
  stroke: var(--muted);
  stroke-width: 1;
  stroke-dasharray: 2 2;
}

.axis {
  font-size: 11px;
  fill: var(--muted);
}

.legend {
  display: flex;
  gap: 14px;
  margin-top: 4px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--muted);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.tip {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  background: rgba(36, 41, 47, 0.92);
  color: #fff;
  border-radius: 5px;
  padding: 6px 9px;
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
  z-index: 2;
}

.tip-ts {
  color: #c9d1d9;
  margin-bottom: 3px;
}

.tip-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tip-row b {
  margin-left: auto;
}

.empty {
  font-size: 12px;
  text-align: center;
  padding: 14px 0;
}
</style>
