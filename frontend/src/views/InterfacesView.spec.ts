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

// P1-6 剩余面：后端 terms size=50 顶格截断会在**不报错**的情况下少露接口
// （真机 7d 请求级 64 种只剩 50）⇒ 页面必须自陈「共 N 种、只显示了 M 种」。
// 判定依据只有 `truncated` —— 拿 `iface_total` 去比会是错的（cardinality 是近似值）。
describe('接口页截断自陈（P1-6）', () => {
  beforeEach(() => {
    metricsMock.metricsInterfaces.mockReset()
    filter.window = '24h'
    filter.agent = ''
  })

  async function mountTruncated(truncated: boolean, ifaceTotal: number) {
    const p = mkPayload()
    p.truncated = truncated
    p.iface_total = ifaceTotal
    metricsMock.metricsInterfaces.mockResolvedValue(p)
    const w = mount(InterfacesView, {
      global: { stubs: { MetricFilterBar: true, RouterLink: true } },
    })
    await flushPromises()
    return w
  }

  it('未截断：不出提示（否则等于天天喊狼来了）', async () => {
    const w = await mountTruncated(false, 1)
    expect(w.find('.trunc-hint').exists()).toBe(false)
  })

  it('截断：同时报出「真实种类数」和「只显示了几个」', async () => {
    const w = await mountTruncated(true, 64)
    const hint = w.find('.trunc-hint')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('64')  // 窗口内共 64 种
    expect(hint.text()).toContain('1')   // 此处只显示 1 种（payload.request 只造了 1 行）
    // 默认序下说的是「请求量最大」——截断丢掉的是**请求量最小的**接口
    expect(hint.text()).toContain('请求量最大')
  })

  it('截断 + error 序：措辞随之改为「错误最多」（同一句在两序下不能都成立）', async () => {
    const w = await mountTruncated(true, 64)
    const th = () => w.findAll('thead th').find((t) => t.text().startsWith('错误'))!
    await th().trigger('click')
    await flushPromises()

    const hint = w.find('.trunc-hint')
    expect(hint.text()).toContain('错误最多')
    expect(hint.text()).not.toContain('请求量最大')
    // 截断提示与排序提示是**两条独立**的行（同用 .hint 样式），别把后者顶掉
    expect(w.text()).toContain('未上榜 ≠ 没出错')
  })
})
