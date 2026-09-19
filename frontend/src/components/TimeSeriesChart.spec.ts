// TimeSeriesChart 单测（P2-23 批 13）。本组件此前**没有任何 spec**（与 MetricCards 批 1-19 时同况）。
// 只钉本批改动的那件事 —— x 轴刻度的**位置生成**与**标签去重**，不铺开测整张图。
//
// 为什么值得测：批 12 的缺陷（`n=123` 时末两刻度只隔 2 桶、标签压在一起 11px）是
// **纯下标算术**，不是 CSS、也不是布局 —— 所以它是本仓少数「jsdom 能真验」的视觉类改动
// （对比批 11 的 `<style scoped>`：jsdom 不应用 scoped CSS，那条路验不了）。
// 下面第 3 条断言就是对着旧实现能红的那条（旧写法末两刻度间距 = 10.85 viewBox px）。
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TimeSeriesChart from './TimeSeriesChart.vue'

const W = 720
const PAD_L = 46
const PAD_R = 12

// 构造 n 行数据。ts 必须逐行不同：标签去重按 xFmt 的**返回值**判重，
// ts 全同会让所有标签相同、被去重成 1 个，几何断言就全废了。
function mkData(n: number): Array<Record<string, number | null>> {
  return Array.from({ length: n }, (_, i) => ({ ts: 1_700_000_000_000 + i * 3_600_000, v: i }))
}

function mountWith(n: number, xFmt: (ts: number) => string = (ts) => String(ts)) {
  return mount(TimeSeriesChart, {
    props: {
      data: mkData(n),
      lines: [{ key: 'v', label: 'v', color: '#000' }],
      xFmt,
      yFmt: (v: number) => String(v),
    },
  })
}

// x 轴刻度文字 = text-anchor="middle" 的 .axis（y 轴那些是 text-anchor="end"）
function tickXs(w: ReturnType<typeof mountWith>): number[] {
  return w.findAll('text.axis[text-anchor="middle"]')
    .map((t) => Number(t.attributes('x')))
}

function tickTexts(w: ReturnType<typeof mountWith>): string[] {
  return w.findAll('text.axis[text-anchor="middle"]').map((t) => t.text())
}

function gaps(xs: number[]): number[] {
  const out: number[] = []
  for (let i = 1; i < xs.length; i++) out.push(xs[i] - xs[i - 1])
  return out
}

describe('TimeSeriesChart x 轴刻度（P2-23）', () => {
  it('n=0：整块不渲染（v-if 短路），不抛异常', () => {
    const w = mountWith(0)
    expect(w.find('svg').exists()).toBe(false)
  })

  it('n=1：1 个刻度、居中，且不因 count-1===0 除零成 NaN', () => {
    const w = mountWith(1)
    const xs = tickXs(w)
    expect(xs).toHaveLength(1)
    expect(Number.isFinite(xs[0])).toBe(true)
    expect(xs[0]).toBeCloseTo(PAD_L + (W - PAD_L - PAD_R) / 2, 6) // 377
  })

  it('n=123（真机实测过的那个 n）：首尾必在、最多 7 个、相邻间距不小于 100 viewBox px', () => {
    // 这条是**判别性回归钉**：旧实现（按 step=floor(123/6)=20 走网格 + 无条件补 122）
    // 的下标是 [0,20,40,60,80,100,120,122] ⇒ 末两刻度间距 = 2×662/122 ≈ 10.85 ⇒ 本条必红。
    const w = mountWith(123)
    const xs = tickXs(w)
    expect(xs).toHaveLength(7)
    expect(xs[0]).toBeCloseTo(PAD_L, 6) // 46，首刻度贴左
    expect(xs[xs.length - 1]).toBeCloseTo(W - PAD_R, 6) // 708，末刻度贴右
    expect(Math.min(...gaps(xs))).toBeGreaterThan(100)
  })

  it('n=8（count< n 且下标会四舍五入跳跃）：7 个刻度、x 严格递增、下标不重复', () => {
    // round(k*7/6) = 0,1,2,4,5,6,7 —— 第 4 个跳到 4（无 3），Set 去重后仍 7 个
    const w = mountWith(8)
    const xs = tickXs(w)
    expect(xs).toHaveLength(7)
    for (let i = 1; i < xs.length; i++) expect(xs[i]).toBeGreaterThan(xs[i - 1])
    expect(xs[0]).toBeCloseTo(PAD_L, 6)
    expect(xs[xs.length - 1]).toBeCloseTo(W - PAD_R, 6)
  })

  it('n ≤ 7：每行都有刻度（不抽稀）', () => {
    for (const n of [2, 5, 7]) {
      expect(tickXs(mountWith(n))).toHaveLength(n)
    }
  })

  it('连续相同标签只渲染第一个（次因去重）', () => {
    // xFmt 恒返回同一天 ⇒ 7 个位置只剩 1 个标签
    const w = mountWith(123, () => '09-15')
    expect(tickTexts(w)).toEqual(['09-15'])
  })

  it('去重只吃「连续」重复：非相邻的重复标签仍保留', () => {
    // 按下标奇偶出标签 ⇒ 选中的下标 [0,20,41,61,81,102,122] 得 A,A,B,B,B,A,A
    // ⇒ 去重后应为 A,B,A：末尾那个 A 与开头的 A 不连续，**必须留**。
    const base = 1_700_000_000_000
    const w = mountWith(123, (ts) => (Math.round((ts - base) / 3_600_000) % 2 === 0 ? 'A' : 'B'))
    const texts = tickTexts(w)
    expect(texts).toEqual(['A', 'B', 'A'])
    for (let i = 1; i < texts.length; i++) expect(texts[i]).not.toBe(texts[i - 1])
  })
})
