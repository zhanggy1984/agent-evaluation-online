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

const ticks = computed(() => {
  const n = rows.value.length
  if (!n) return [] as number[]
  const step = Math.max(1, Math.floor(n / 6))
  const out: number[] = []
  for (let i = 0; i < n; i += step) out.push(i)
  if (!out.includes(n - 1)) out.push(n - 1)
  return out
})

const gridVals = computed(() => {
  const { min, max } = yDomain.value
  return [0, 1, 2, 3, 4].map((i) => min + ((max - min) * i) / 4)
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
        <text :x="PAD_L - 4" :y="yAt(gv) + 3" text-anchor="end" class="axis">
          {{ i === 0 || i === gridVals.length - 1 ? yFmt(gv) : '' }}
        </text>
      </g>
      <path
        v-for="l in lines" :key="l.key" :d="linePath(l)"
        :style="{ stroke: l.color }" fill="none" stroke-width="2" stroke-linejoin="round"
      />
      <template v-if="hover !== null">
        <line :x1="guideX()" :x2="guideX()" :y1="PAD_T" :y2="H - PAD_B" class="guide" />
        <circle
          v-for="(d, k) in hoverDots" :key="`d${k}`"
          :cx="d.x" :cy="d.y" r="3.5" :style="{ fill: d.color }"
        />
      </template>
      <text
        v-for="(ti, k) in ticks" :key="`t${k}`"
        :x="xAt(ti)" :y="H - 6" text-anchor="middle" class="axis"
      >{{ xFmt(rowTs(ti)) }}</text>
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

.grid {
  stroke: var(--border);
  stroke-width: 1;
  stroke-dasharray: 2 3;
}

.guide {
  stroke: var(--muted);
  stroke-width: 1;
  stroke-dasharray: 2 2;
}

.axis {
  font-size: 10px;
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
