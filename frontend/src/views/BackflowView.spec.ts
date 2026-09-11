// 回流看板列表页组件挂载测试（C2）。
// 风险集中在：① 首屏四个并发拉取（agent 下拉/接口下拉/总览/列表）各自失败不得互相拖垮；
// ② 筛选与分页拼出的请求参数（空串必须转成「不发该参数」而非 `layer=`）；
// ③ 行内 trace 跳转的 stopPropagation——漏了会连行点击一起触发，一次点击跳两次路由；
// ④ 二期入口（弃留墙/quality）在本页必须**纯未渲染**（detail §9.1 注记）。
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { BackflowCluster, BackflowOverview } from '../api/types'
import BackflowView from './BackflowView.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const apiMock = vi.hoisted(() => ({
  backflowOverview: vi.fn(),
  backflowClusters: vi.fn(),
  metricsInterfaces: vi.fn(),
}))
vi.mock('../api/backflow', () => ({
  backflowOverview: apiMock.backflowOverview,
  backflowClusters: apiMock.backflowClusters,
}))
vi.mock('../api/metrics', () => ({ metricsInterfaces: apiMock.metricsInterfaces }))

const agentsMock = vi.hoisted(() => ({ load: vi.fn(), agents: [] as string[] }))
vi.mock('../composables/useAgents', () => ({
  useAgents: () => ({
    agents: agentsMock.agents, loading: { value: false },
    errorMsg: { value: '' }, load: agentsMock.load,
  }),
}))

function row(over: Partial<BackflowCluster> = {}): BackflowCluster {
  return {
    cluster_id: 1, agent: 'a-1', interface: 'POST /api/chat', layer: 'L1',
    error_type: 'llm_timeout', error_msg: '超时', input_hash: 'h', first_trace_id: 't-1',
    input_truncated: 0, generation: 1, count: 2, status: 'open',
    first_ts: '2026-09-01T00:00:00', latest_ts: '2026-09-10T00:00:00',
    fix_version: null, claimed_by: null, claimed_at: null, claim_due_ts: null,
    claim_k: 2, needs_review_reason: null, link: null, ...over,
  }
}

const emptyOverview: BackflowOverview = {
  clusters: {}, links: {}, by_agent: [], to_fix: 0,
} as unknown as BackflowOverview

interface MountOpts {
  items?: BackflowCluster[]
  total?: number
  // 注入口：错误必须在 mount 前装配好，不能 mount 后用 mockResolvedValue 覆盖
  // （覆盖会静默把 reject 变 resolve，造出「测失败路径但实际走成功路径」的假绿）
  overviewError?: unknown
  ifacesError?: unknown
}

async function mountView(opts: MountOpts = {}) {
  if (opts.overviewError !== undefined) apiMock.backflowOverview.mockRejectedValue(opts.overviewError)
  else apiMock.backflowOverview.mockResolvedValue(emptyOverview)
  apiMock.backflowClusters.mockResolvedValue({
    items: opts.items ?? [], total: opts.total ?? (opts.items?.length ?? 0),
    page: 1, page_size: 20,
  })
  if (opts.ifacesError !== undefined) apiMock.metricsInterfaces.mockRejectedValue(opts.ifacesError)
  else apiMock.metricsInterfaces.mockResolvedValue({ request: [], llm: [] })
  const w = mount(BackflowView)
  await flush()
  return w
}

const flush = async () => { for (let i = 0; i < 4; i++) await Promise.resolve() }

// 不用 Array.prototype.at（本仓 tsconfig 的 lib 目标低于 es2022，编译期不认识）
const lastQuery = () => {
  const calls = apiMock.backflowClusters.mock.calls
  return calls[calls.length - 1][0]
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  // agent 下拉的 <option> 由 v-for 生成：不预置选项时 select 无法保持选定值（浏览器会回落到空项）
  agentsMock.agents = ['a-9', 'a-8']
})

afterEach(() => { vi.unstubAllGlobals() })

describe('首屏', () => {
  it('挂载即发四个请求：agent 下拉 / 接口下拉 / 总览 / 列表(page=1, size=20)', async () => {
    await mountView()
    expect(agentsMock.load).toHaveBeenCalled()
    expect(apiMock.metricsInterfaces).toHaveBeenCalledWith(null, '7d')
    expect(apiMock.backflowOverview).toHaveBeenCalledTimes(1)
    expect(apiMock.backflowClusters).toHaveBeenCalledTimes(1)
    expect(lastQuery()).toEqual({ page: 1, page_size: 20 })
  })

  it('空结果 → 命中态文案，且不渲染表体与分页', async () => {
    const w = await mountView()
    expect(w.text()).toContain('无命中 cluster')
    expect(w.findAll('tbody tr')).toHaveLength(0)
    expect(w.find('.page-no').exists()).toBe(false)
  })

  it('接口下拉失败不影响主体（可选筛选项，静默留空）', async () => {
    const w = await mountView({ items: [row()], ifacesError: new Error('boom') })
    expect(w.findAll('tbody tr')).toHaveLength(1)
    expect(w.findAll('select')).toHaveLength(5)
    // 失败后 interface 下拉只剩「全部接口」+ 可能的「载入中…」
    expect(w.findAll('select')[1].findAll('option').length).toBeLessThanOrEqual(2)
  })

  it('总览失败 → 只出总览错误行，列表照常渲染', async () => {
    const { ApiError } = await import('../api/client')
    const w = await mountView({
      items: [row()], overviewError: new ApiError(500, 'ERR_X', '炸了'),
    })
    expect(w.text()).toContain('总览加载失败')
    expect(w.text()).toContain('ERR_X')
    expect(w.findAll('tbody tr')).toHaveLength(1)
  })

  it('列表失败 → 错误文案 + 表体清空（不留过期数据）', async () => {
    const { ApiError } = await import('../api/client')
    const w = await mountView()
    apiMock.backflowClusters.mockRejectedValue(new ApiError(500, 'ERR_X', '炸了'))
    await w.find('button[type="submit"]').trigger('submit')
    await flush()
    expect(w.text()).toContain('查询失败（ERR_X）')
    expect(w.findAll('tbody tr')).toHaveLength(0)
  })
})

describe('筛选参数拼装', () => {
  it('五个下拉按序生效，空串不下发（不产生 layer= 这类空筛）', async () => {
    const w = await mountView()
    const sels = w.findAll('select')
    await sels[0].setValue('a-9')                       // agent
    await sels[2].setValue('L2')                        // layer
    await sels[3].setValue('fixed')                     // status
    await sels[4].setValue('invalidated')               // watch
    await w.find('button[type="submit"]').trigger('submit')
    await flush()

    expect(lastQuery()).toEqual({
      agent: 'a-9', layer: 'L2', status: 'fixed', watch: 'invalidated',
      page: 1, page_size: 20,
    })
  })

  it('筛选后回到第 1 页（不清页码会落在空页）', async () => {
    const w = await mountView({ items: Array.from({ length: 20 }, (_, i) => row({ cluster_id: i + 1 })), total: 40 })
    await w.findAll('button').find(b => b.text().includes('下一页'))!.trigger('click')
    await flush()
    expect(lastQuery().page).toBe(2)

    await w.findAll('select')[3].setValue('open')
    await w.find('button[type="submit"]').trigger('submit')
    await flush()
    expect(lastQuery().page).toBe(1)
  })

  it('agent 下拉项来自 useAgents（含空项「全站 agent」共 N+1 个 option）', async () => {
    const w = await mountView()
    const opts = w.findAll('select')[0].findAll('option')
    expect(opts.map(o => o.text())).toEqual(['全站 agent', 'a-9', 'a-8'])
  })
})

describe('分页', () => {
  it('total ≤ pageSize → 整块分页不渲染', async () => {
    const w = await mountView({ items: [row()], total: 20 })
    expect(w.find('.page-no').exists()).toBe(false)
  })

  it('满页 20 条且 total 更大 → 下一页可点，页码文本正确', async () => {
    const items = Array.from({ length: 20 }, (_, i) => row({ cluster_id: i + 1 }))
    const w = await mountView({ items, total: 45 })
    expect(w.find('.page-no').text()).toBe('1 / 3')
    const next = w.findAll('button').find(b => b.text().includes('下一页'))!
    expect((next.element as HTMLButtonElement).disabled).toBe(false)
    await next.trigger('click')
    await flush()
    expect(lastQuery().page).toBe(2)
  })

  it('首页「上一页」禁用；末页「下一页」禁用', async () => {
    const items = Array.from({ length: 20 }, (_, i) => row({ cluster_id: i + 1 }))
    const w = await mountView({ items, total: 45 })
    const prev = () => w.findAll('button').find(b => b.text().includes('上一页'))!
    expect((prev().element as HTMLButtonElement).disabled).toBe(true)   // page=1

    await w.findAll('button').find(b => b.text().includes('下一页'))!.trigger('click')
    await flush()
    await w.findAll('button').find(b => b.text().includes('下一页'))!.trigger('click')
    await flush()
    expect(w.find('.page-no').text()).toBe('3 / 3')
    expect((w.findAll('button').find(b => b.text().includes('下一页'))!.element as HTMLButtonElement).disabled)
      .toBe(true)
  })

  it('未满页即禁用下一页（防跳到必然空页）', async () => {
    const w = await mountView({ items: [row()], total: 45 })
    const next = w.findAll('button').find(b => b.text().includes('下一页'))!
    expect((next.element as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('跳转', () => {
  it('行点击 → cluster 详情路由，params 带 clusterId', async () => {
    const w = await mountView({ items: [row({ cluster_id: 42 })] })
    await w.find('tbody tr').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'backflow-cluster', params: { clusterId: 42 } })
  })

  it('trace 链接点击 → 只跳 trace 详情**一次**（stopPropagation 挡住行点击）', async () => {
    const w = await mountView({ items: [row({ agent: 'a-1', first_trace_id: 't-9' })] })
    await w.find('button.link-like').trigger('click')
    expect(push).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith({
      name: 'trace-detail', params: { agent: 'a-1', traceId: 't-9' },
    })
  })

  it('first_trace_id 为空 → 不渲染 trace 按钮（不给死链）', async () => {
    const w = await mountView({ items: [row({ first_trace_id: null })] })
    expect(w.find('button.link-like').exists()).toBe(false)
  })
})

describe('字段与边界', () => {
  it('状态 pill 显示中文 + class 带原始枚举', async () => {
    const w = await mountView({ items: [row({ status: 'needs_review' })] })
    const pill = w.find('td .status')
    expect(pill.text()).toBe('待人工复核')
    expect(pill.classes()).toContain('st-needs_review')
  })

  it('未知状态 → 原文兜底（不显示 undefined）', async () => {
    const w = await mountView({ items: [row({ status: 'brand_new' })] })
    expect(w.find('td .status').text()).toBe('brand_new')
  })

  it('gen>1 才显示代数标记', async () => {
    const on = await mountView({ items: [row({ generation: 3 })] })
    expect(on.text()).toContain('gen3')
    const off = await mountView({ items: [row({ generation: 1 })] })
    expect(off.text()).not.toContain('gen1')
  })

  it('时间戳 null → 显示「-」而非 1970（后端空值不外泄为纪元）', async () => {
    const w = await mountView({ items: [row({ first_ts: null, latest_ts: null })] })
    const cells = w.findAll('tbody tr td')
    expect(cells.some(c => c.text() === '-')).toBe(true)
    expect(w.text()).not.toContain('1970')
  })

  it('二期入口在本页零渲染（detail §9.1：弃留墙/quality 不从本页引）', async () => {
    const w = await mountView({ items: [row()] })
    expect(w.text()).not.toContain('弃留墙')
    expect(w.text().toLowerCase()).not.toContain('quality')
  })

  it('现行 link 摘要：取 items[0].link 的 offline 语义', async () => {
    const w = await mountView({
      items: [row({ link: {
        link_id: 1, payload_id: 'p', case_id: 'c', case_type: 'replay',
        offline_status: 'invalidated', verify_status: 'pending',
        assembled_ts: null, invalidate_reason: null, requeue_count: 0,
      } })],
    })
    expect(w.text()).toContain('现行 link')
    expect(w.text()).toContain('invalidated')
  })
})
