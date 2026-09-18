// 接口页排序交互（P1-6）——只钉一件事：**在 LLM 级 tab 点「失败」排序后仍留在该 tab**。
//
// 为什么单独立这条：真机实测撞到过回归。原实现只有一个 watch（agent/window/sort 合体），
// 排序变化时 `payload.value = null` ⇒ `v-else-if="payload"` 卸载 `<InterfacesSection>`，
// 而「请求级/LLM 级」tab 是**该组件的内部 ref** ⇒ 重挂时重置回 'request'。
// 症状 = 用户点自己那个 tab 的表头，页面跳到另一个 tab（数据其实是对的，所以不报错）。
// 这条断言是**判别性**的：砍掉 sort 那个独立 watch、退回合体 watch，本用例必红。
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MetricsInterfaces } from '../api/types'
import InterfacesView from './InterfacesView.vue'

const metricsMock = vi.hoisted(() => ({ metricsInterfaces: vi.fn() }))
vi.mock('../api/metrics', () => metricsMock)

// 本页只在「从接口页带筛选跳过来」的落点上间接依赖路由；这里给最小可用替身。
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))

const filter = reactive({ window: '24h', agent: '' })
vi.mock('../composables/useMetricFilter', () => ({ useMetricFilter: () => ({ filter }) }))

function mkPayload(): MetricsInterfaces {
  return {
    source: 'realtime',
    fallback_hours: [],
    request: [{ interface: 'POST /chat', total: 10, error: 2, timeout: 0, p50: 1, p95: 2, p99: 3 }],
    llm: [{ interface: 'POST /chat', total: 5, error: 1, llm_failure_rate: 0.2, models: [] }],
  } as unknown as MetricsInterfaces
}

async function mountView() {
  metricsMock.metricsInterfaces.mockResolvedValue(mkPayload())
  const w = mount(InterfacesView, {
    global: { stubs: { MetricFilterBar: true, RouterLink: true } },
  })
  await flushPromises()
  return w
}

describe('接口页排序（P1-6）', () => {
  beforeEach(() => {
    metricsMock.metricsInterfaces.mockReset()
    filter.window = '24h'
    filter.agent = ''
  })

  it('在 LLM 级 tab 点「失败」排序：仍留在 LLM 级 tab，并把 sort=error 传下去', async () => {
    const w = await mountView()

    await w.findAll('.tabs button')[1].trigger('click') // 切到 LLM 级
    expect(w.findAll('.tabs button')[1].classes()).toContain('on')

    const failTh = w.findAll('thead th').find((t) => t.text().startsWith('失败'))
    expect(failTh, 'LLM 级 tab 的「失败」表头必须可点').toBeTruthy()
    await failTh!.trigger('click')
    await flushPromises()

    // ① 参数确实传下去了（组件层；URL 层由 api/metrics.spec.ts 钉）
    expect(metricsMock.metricsInterfaces).toHaveBeenLastCalledWith(null, '24h', 'error')
    // ② 关键：tab 没被重置（payload 未清空 ⇒ section 未卸载）
    const tabs = w.findAll('.tabs button')
    expect(tabs[1].classes()).toContain('on')
    expect(tabs[0].classes()).not.toContain('on')
  })

  it('再点一次回到默认排序，且同样留在原 tab', async () => {
    const w = await mountView()
    await w.findAll('.tabs button')[1].trigger('click')

    const th = () => w.findAll('thead th').find((t) => t.text().startsWith('失败'))!
    await th().trigger('click')
    await flushPromises()
    expect(metricsMock.metricsInterfaces).toHaveBeenLastCalledWith(null, '24h', 'error')

    await th().trigger('click')
    await flushPromises()
    // 回到默认：第三个实参回到 null（不是空串、也不是漏传）
    expect(metricsMock.metricsInterfaces).toHaveBeenLastCalledWith(null, '24h', null)
    expect(w.findAll('.tabs button')[1].classes()).toContain('on')
  })
})
