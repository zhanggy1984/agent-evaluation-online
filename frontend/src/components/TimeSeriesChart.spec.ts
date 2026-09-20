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

// —— 孤立点可见性（2026-09-20，/dashboard 7d 真机取证驱动）——
// 真机读数：error_rate 的连续非空段长分布 = [1,3,1,2,2,1]，6 段里 3 段长 1。
// 长度 1 的段在 linePath 里只产出 "M x y"，SVG 中只有 moveto 的路径**什么都不画** ⇒
// count=68（失败率 1.47%）这样的真实读点彻底不可见。修复 = 单独收集并画成圆点。
describe('TimeSeriesChart 孤立点', () => {
  const line = [{ key: 'v', label: 'v', color: '#000' }]

  function mountSeries(vals: Array<number | null>) {
    return mount(TimeSeriesChart, {
      props: {
        data: vals.map((v, i) => ({ ts: 1_700_000_000_000 + i * 3_600_000, v })),
        lines: line,
        xFmt: (ts: number) => String(ts),
        yFmt: (v: number) => String(v),
      },
    })
  }

  it('前后皆空的单点会渲染成一个圆点（旧实现下这个点完全不可见）', () => {
    const w = mountSeries([null, 5, null])
    expect(w.findAll('circle')).toHaveLength(1)
  })

  it('两点以上的连续段不产生圆点（它们本来就画得出来）', () => {
    const w = mountSeries([null, 5, 6, null])
    expect(w.findAll('circle')).toHaveLength(0)
  })

  it('一条线里多个孤立点各出一个圆点，互不合并', () => {
    // 段长分布 [1,1,1]：三个孤立点必须全部可见（真机那一次是 [1,3,1,2,2,1]）
    expect(mountSeries([1, null, 2, null, 3]).findAll('circle')).toHaveLength(3)
  })

  it('全空序列不产生圆点，也不抛错', () => {
    const w = mountSeries([null, null])
    expect(w.findAll('circle')).toHaveLength(0)
  })
})

// —— y 轴刻度（2026-09-20，/dashboard 观感走查驱动）——
// 旧实现：模板里 `i === 0 || i === gridVals.length - 1 ? yFmt(gv) : ''` ⇒
// 画了 5 条网格线、**只有 2 条能读出数**，中间三条是无标签的装饰线。
describe('TimeSeriesChart y 轴刻度', () => {
  // y 轴标签 = text-anchor="end" 的 .axis（x 轴那些是 middle）。
  // ⚠️ `.filter(Boolean)` **不是**洁癖，它是本组测试的判别力来源：旧实现同样渲染 5 个
  // <text> 元素，只是其中 3 个的文本是空串（模板三元判断给的 ''）⇒ 若只数元素个数，
  // 旧实现也「通过」。**数元素 ≠ 数有值的标签**，这是本条第一次写出来时的假绿。
  const yTexts = (w: ReturnType<typeof mountWith>): string[] =>
    w.findAll('text.axis[text-anchor="end"]').map((t) => t.text()).filter(Boolean)

  it('五条网格线全部标值（旧实现只有 2 个非空标签 ⇒ 本条对它必红）', () => {
    const w = mountWith(5) // v = 0..4 ⇒ 值域 [0,4] ⇒ 网格值 0/1/2/3/4，互不相同
    expect(yTexts(w)).toEqual(['0', '1', '2', '3', '4'])
  })

  it('相邻标签文案重复时只留第一个（量程极小时 yFmt 会把两个值格式化成同一串）', () => {
    const w = mount(TimeSeriesChart, {
      props: {
        data: mkData(5),
        lines: [{ key: 'v', label: 'v', color: '#000' }],
        xFmt: (ts: number) => String(ts),
        yFmt: () => '0.00%', // 五位小数都撞在一起 ⇒ 五个刻度其实是同一个读数
      },
    })
    expect(yTexts(w)).toEqual(['0.00%'])
  })
})
