// 总览页 7d 分位注的**归因方向**（批 40 · 任务 #37）。
// 判别性所在 —— 旧文案写「汇总只到上一个整点，之后的流量不计入分位」，把"未计入分位"归因到
// **尾部**；实测 `covered_hours`(45) 与窗口(168) 的差 98% 来自**头部**（rollup 起点之前的时段：
// 7d 窗内 request 事件 1396 条，落在 rollup 覆盖期内的仅 28 条）。旧措辞会让读者以为"只差最后
// 一个小时"，从而反复追问这个数怎么来的（用户正是这么问的）。
// 故正向钉住新文案把两侧都说清：「本窗内未汇总的时段」（头部 + 中间缺口）与「进行中的整点」（尾部）。
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MetricsOverview } from '../api/types'
import { useMetricFilter, type WindowKey } from '../composables/useMetricFilter'
import OverviewView from './OverviewView.vue'

const apiMock = vi.hoisted(() => ({ metricsOverview: vi.fn() }))
vi.mock('../api/metrics', () => apiMock)

function overview(source: string, covered: number): MetricsOverview {
  return {
    window: '7d',
    agent: null,
    source,
    fallback_hours: [],
    covered_hours: covered,
    cards: {
      qps: 1.5, p50: 12, p95: 40, p99: 88,
      total: 100, error: 3, timeout: 1, error_rate: 0.03, timeout_rate: 0.01,
    },
    series: [],
  }
}

/** 挂载并等首屏 load 落地（onMounted 里 void load() → await metricsOverview） */
async function mountView(win: WindowKey, source: string, covered: number) {
  useMetricFilter().filter.window = win
  apiMock.metricsOverview.mockResolvedValue(overview(source, covered))
  const w = mount(OverviewView)
  await Promise.resolve()
  await Promise.resolve()
  return w
}

beforeEach(() => {
  apiMock.metricsOverview.mockReset()
})

describe('7d 分位口径注（批 40 归因订正）', () => {
  it('mixed：两侧未计入都写清，且不再把缺口说成只在尾部', async () => {
    const w = await mountView('7d', 'mixed', 45)
    const note = w.find('.note').text()
    expect(note).toContain('基于 45 个小时的汇总数据')
    // 头部 / 中间缺口：本窗内未汇总的时段
    expect(note).toContain('本窗内未汇总的时段')
    // 尾部：进行中的整点
    expect(note).toContain('进行中的整点')
    expect(note).toContain('不计入分位')
    // 旧措辞（把缺口归因到"之后"）必须已消失——否则读者仍会以为只差最后一个小时
    expect(note).not.toContain('之后的流量')
  })

  it('数字随 covered_hours 变（注不是写死的文案）', async () => {
    const w = await mountView('7d', 'mixed', 120)
    expect(w.find('.note').text()).toContain('基于 120 个小时的汇总数据')
  })

  it('1h/24h 与 realtime 不渲染该注（注只属于 7d 且走 rollup 读路径时）', async () => {
    const w24 = await mountView('24h', 'realtime', 0)
    expect(w24.find('.note').exists()).toBe(false)

    const wReal = await mountView('7d', 'realtime', 0)
    expect(wReal.find('.note').exists()).toBe(false)
  })
})
