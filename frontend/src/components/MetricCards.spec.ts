// MetricCards 单测（P1-19）。本组件此前**没有任何 spec**（src/components/ 下 0 个）。
// 这里只钉两件本批改动的事，不铺开测全部卡片：
//   ① 标题是「平均 QPS」——后端口径是 total/整窗秒数（整窗平均），与同页图表的桶口径不同，
//      标题不区分会被读成同一个数；
//   ② 7d 窗的小速率不再显示成 0.00 —— 379/604800 是真实读数（379 次请求 / 7 天），
//      改前 toFixed(2) 把它压成 '0.00'，读起来是「没有」而不是「很小」。
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { MetricsCards as CardsData } from '../api/types'
import MetricCards from './MetricCards.vue'

function mkCards(qps: number): CardsData {
  return {
    qps, p50: 12, p95: 30, p99: 80, total: 379, error: 3, timeout: 0,
    error_rate: 0.0079, timeout_rate: 0,
  } as unknown as CardsData
}

describe('MetricCards（P1-19）', () => {
  it('速率卡标题是「平均 QPS」（点明整窗平均口径）', () => {
    const w = mount(MetricCards, { props: { cards: mkCards(1), loading: false } })
    const labels = w.findAll('.lab').map((l) => l.text())
    expect(labels).toContain('平均 QPS')
    expect(labels).not.toContain('QPS')
  })

  it('7d 窗的小速率渲染成 0.000627，不是 0.00', () => {
    const w = mount(MetricCards, {
      props: { cards: mkCards(379 / 604800), loading: false },
    })
    const cells = w.findAll('.card')
    const qpsCell = cells.find((c) => c.find('.lab').text() === '平均 QPS')!
    expect(qpsCell.find('b').text()).toBe('0.000627')
  })
})
