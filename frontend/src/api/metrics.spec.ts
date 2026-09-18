// P1-6 补测：metricsInterfaces 的 sort 参数**透传**（真取 URL，不 mock 本模块）。
//
// 为什么单独立这个文件：InterfacesView 的单测是 `vi.mock('../api/metrics')` 的 ——
// 它只能证明「组件把 sort 传给了 metricsInterfaces」，**结构性地证明不了「它把 sort 发出去」**。
// 这与 2026-09-18 P1-11 的事故是同一层（listTraces 漏发 status，mock 边界正好遮住断点，
// 见 traces.spec.ts 文件头）。⇒ 本文件把「sort 真的进了 URL」钉死在最外层。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMock = vi.hoisted(() => vi.fn())
vi.mock('./client', () => ({ api: apiMock }))

import { metricsInterfaces } from './metrics'

/** 取第 n 次调用传给 api() 的 path（第 0 个实参） */
const pathOf = (n = 0): string => apiMock.mock.calls[n][0] as string

describe('P1-6 metricsInterfaces 参数透传', () => {
  beforeEach(() => {
    apiMock.mockReset()
    apiMock.mockResolvedValue({ request: [], llm: [] })
  })

  it('sort="error" 必须进 URL', async () => {
    await metricsInterfaces(null, '24h', 'error')
    expect(pathOf()).toContain('sort=error')
    expect(pathOf()).toContain('window=24h')
  })

  it('不传 sort → URL 里不出现该参数（默认口径 = 按请求量降序）', async () => {
    await metricsInterfaces(null, '24h')
    expect(pathOf()).not.toContain('sort')
  })

  it('sort=null 与省略同效（调用方用 `sort.value || null` 传参）', async () => {
    await metricsInterfaces(null, '24h', null)
    expect(pathOf()).not.toContain('sort')
  })

  it('sort 与 agent/window 并列时一个都不丢（防只补一个新的就挤掉旧的）', async () => {
    await metricsInterfaces('cc', '7d', 'error')
    const p = pathOf()
    for (const kv of ['agent=cc', 'window=7d', 'sort=error']) {
      expect(p).toContain(kv)
    }
  })
})
