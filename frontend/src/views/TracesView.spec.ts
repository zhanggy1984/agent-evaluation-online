// 链路查询页分页边界测试（批 6 · P1-10）。
// 改动点：分母由写死的 DEEP_PAGE_LIMIT(=10) 改为 max(1, min(10, ceil(total/pageSize)))。
// 判别性所在：**只有 20 < total < 200 时新旧逻辑输出才不同** ——
//   total ≤ 20     → 分页行整块不渲染（`v-if="total > pageSize"`），新旧同形；
//   total ≥ 200    → min(10, ceil(total/20)) 恒为 10，新旧同形（真机默认视图 total=1952 即此例，
//                    ≈ 我第一次取证读到「1 / 10」与改前一字不差、零判别力的原因）；
//   20 < total<200 → 新逻辑给出 2..9，旧逻辑恒 10 ⇒ **本文件的价值全在这一段**。
// 手法：mock 掉 vue-router 与 api 模块（含 useAgents），断言渲染出的分母文案与翻页按钮态，不碰网络。
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TraceListItem } from '../api/types'
import TracesView from './TracesView.vue'

const push = vi.fn()
// P1-11：本页现在也读 useRoute().query（「从接口页带筛选跳过来」的落点）——
// 不 mock useRoute 会让本文件**全部**用例红（useRoute() 得 undefined ⇒ route.query 抛错）。
const routeQuery = vi.hoisted(() => ({ value: {} as Record<string, string> }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ query: routeQuery.value }),
}))

const apiMock = vi.hoisted(() => ({ listTraces: vi.fn() }))
vi.mock('../api/traces', () => apiMock)

// useAgents 返回的是 ref（模板里自动解包）⇒ 必须给真 ref，不能用 { value: [] } 冒充
vi.mock('../composables/useAgents', async () => {
  const { ref } = await import('vue')
  return {
    useAgents: () => ({
      agents: ref<string[]>([]), loading: ref(false), errorMsg: ref(''), load: vi.fn(),
    }),
    // 显示名映射的内容（中文名）由真机验证覆盖；此处按恒等放行，避免单测锁死文案。
    agentDisplay: (n: string) => n,
  }
})

function row(i: number): TraceListItem {
  return {
    ts: 1758000000000, agent: 'a-1', trace_id: `t-${i}`, interface: 'POST /api/chat',
    node: 'n-1', status: 'ok', error_type: null, error_msg: null,
  } as TraceListItem
}

/** 挂载并等首屏 doSearch 落地（onMounted 里是 void doSearch(1) → await listTraces） */
async function mountView(res: { items: TraceListItem[]; total: number }) {
  apiMock.listTraces.mockResolvedValue(res)
  const w = mount(TracesView)
  await Promise.resolve()
  await Promise.resolve()
  return w
}

const pageNo = (w: ReturnType<typeof mount>) => w.find('.page-no')
const nextBtn = (w: ReturnType<typeof mount>) =>
  w.findAll('button').find(b => b.text().includes('下一页'))

describe('P1-10 后半（2026-09-20）时间窗控件', () => {
  beforeEach(() => { apiMock.listTraces.mockReset(); push.mockReset(); routeQuery.value = {} })

  // ⚠️ **按下标取 select 是脆的**：2026-09-20 在 agent 与时间窗之间插入「状态」下拉后，
  // 原来写的 `[1]` 直接指到了状态下拉 —— 本用例仍会「跑得过」，但量的已是另一个控件。
  // 故改为**按选项文案认领**（改的是「取哪个元素」，不是断言）。
  // 顺序：[0] agent · [1] 状态 · [2] 时间窗
  const winSel = (w: ReturnType<typeof mount>) =>
    w.findAll('select').filter(s => s.text().includes('近 1 小时'))[0]

  it('首屏按默认 7d 发 start_ts（= now - 7d，容差 60s 容忍用例自身耗时）', async () => {
    await mountView({ items: [], total: 0 })
    const q = apiMock.listTraces.mock.calls[0][0]
    const delta = Date.now() - q.start_ts
    expect(delta).toBeGreaterThan(7 * 86400e3 - 60_000)
    expect(delta).toBeLessThan(7 * 86400e3 + 60_000)
  })

  it('切到「近 1 小时」⇒ 真的重发请求，且 start_ts 收窄到 1h 量级', async () => {
    const w = await mountView({ items: [], total: 0 })
    apiMock.listTraces.mockClear()
    await winSel(w).setValue('1h')
    await Promise.resolve()
    expect(apiMock.listTraces).toHaveBeenCalled()
    const q = apiMock.listTraces.mock.calls[0][0]
    expect(Date.now() - q.start_ts).toBeLessThan(2 * 3600e3)
  })

  it('切窗必须回到第 1 页（否则会停在旧范围算出的、现已越界的页码上）', async () => {
    // ⚠️ 必须给满一页（pageSize=20）：下一页按钮的 disabled 是
    // `page >= maxPages || items.length < pageSize`，给不满时点击**静默无效**。
    const w = await mountView({ items: Array.from({ length: 20 }, (_, i) => row(i)), total: 60 })
    await nextBtn(w)!.trigger('click')
    await Promise.resolve()
    const calls = apiMock.listTraces.mock.calls
    expect(calls[calls.length - 1][0].page).toBe(2)
    apiMock.listTraces.mockClear()
    await winSel(w).setValue('24h')
    await Promise.resolve()
    expect(apiMock.listTraces.mock.calls[0][0].page).toBe(1)
  })

  it('切到与当前相同的档 ⇒ 不重发（下拉 change 会抖，别白打一次请求）', async () => {
    const w = await mountView({ items: [], total: 0 })
    apiMock.listTraces.mockClear()
    await winSel(w).setValue('7d')
    await Promise.resolve()
    expect(apiMock.listTraces).not.toHaveBeenCalled()
  })
})

describe('P1-10 分页分母', () => {
  beforeEach(() => { apiMock.listTraces.mockReset(); push.mockReset(); routeQuery.value = {} })

  it('total=30 → 分母 2（改前写死 10，是本条唯一的判别窗口）', async () => {
    const w = await mountView({ items: [], total: 30 })
    expect(pageNo(w).text()).toBe('1 / 2')
  })

  it('total=25 → 分母 2（向上取整）', async () => {
    const w = await mountView({ items: [], total: 25 })
    expect(pageNo(w).text()).toBe('1 / 2')
  })

  it('total=21 → 分母 2（刚过一页即 2，不是 1）', async () => {
    const w = await mountView({ items: [], total: 21 })
    expect(pageNo(w).text()).toBe('1 / 2')
  })

  it('total=21 与 total=30 都必须小于上限 10 —— 防止有人把 min 写反', async () => {
    const a = await mountView({ items: [], total: 21 })
    expect(pageNo(a).text()).not.toBe('1 / 10')
    const b = await mountView({ items: [], total: 30 })
    expect(pageNo(b).text()).not.toBe('1 / 10')
  })

  it('total=200 → 分母 10（恰好到上限）', async () => {
    const w = await mountView({ items: [], total: 200 })
    expect(pageNo(w).text()).toBe('1 / 10')
  })

  it('total=1952（真机默认视图）→ 分母仍 10，与改前同形（非判别，仅锁定不回退）', async () => {
    const w = await mountView({ items: [], total: 1952 })
    expect(pageNo(w).text()).toBe('1 / 10')
  })

  it('total=20（恰好一页）→ 整个分页行不渲染', async () => {
    const w = await mountView({ items: [], total: 20 })
    expect(pageNo(w).exists()).toBe(false)
  })

  it('total=0 → 不渲染分页，也不显示 NaN/0（max(1, …) 的下界）', async () => {
    const w = await mountView({ items: [], total: 0 })
    expect(pageNo(w).exists()).toBe(false)
    expect(w.text()).not.toContain('NaN')
  })
})

describe('P1-10 翻页边界', () => {
  beforeEach(() => { apiMock.listTraces.mockReset(); routeQuery.value = {} })

  it('翻到末页 → 分母 2/2 且「下一页」禁用', async () => {
    // 第 1 页满页（20 条）⇒ 启用下一页；第 2 页只回 10 条 ⇒ 到末页
    apiMock.listTraces
      .mockResolvedValueOnce({ items: Array.from({ length: 20 }, (_, i) => row(i)), total: 30 })
      .mockResolvedValueOnce({ items: Array.from({ length: 10 }, (_, i) => row(i)), total: 30 })
    const w = mount(TracesView)
    await Promise.resolve(); await Promise.resolve()
    expect(pageNo(w).text()).toBe('1 / 2')
    expect((nextBtn(w)!.element as HTMLButtonElement).disabled).toBe(false)

    await nextBtn(w)!.trigger('click')
    await Promise.resolve(); await Promise.resolve()
    expect(pageNo(w).text()).toBe('2 / 2')
    expect((nextBtn(w)!.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('⚠️ 「下一页」禁用不是本条的判别面：满页时旧逻辑也会禁用（items.length < pageSize 独立成立）', async () => {
    // 第 1 页只回 10 条（< pageSize）⇒ 即使 page(1) < maxPages(2)，仍禁用。
    // **刻意不断言分母**：本条的判据只有 disabled —— 判别性回退（把分母改回写死 10）时
    // 它应当**仍然绿**，这才自证「这一面区分不了新旧逻辑」；带了分母断言反而会红，
    // 把同形面伪装成判别面。真机取证时我正是差点据此误判，故在此钉死。
    const w = await mountView({ items: Array.from({ length: 10 }, (_, i) => row(i)), total: 30 })
    expect((nextBtn(w)!.element as HTMLButtonElement).disabled).toBe(true)
  })
})

// P1-11：接口页的错误数跳进来时带 interface + status —— 本组钉「URL 真被消费」与
// 「隐形筛选被显式告知」。⚠️ 本组**不证明**条数等于接口页那个数字（口径不同，见 es.py 内警告）。
describe('P1-11 URL 带筛选落地', () => {
  beforeEach(() => { apiMock.listTraces.mockReset(); routeQuery.value = {} })

  it('URL 带 interface + status → 首屏查询即带上这两个参数', async () => {
    routeQuery.value = { interface: 'POST /api/chat/{id}', status: 'error' }
    await mountView({ items: [], total: 29 })
    expect(apiMock.listTraces).toHaveBeenCalledWith(
      expect.objectContaining({ interface: 'POST /api/chat/{id}', status: 'error' }),
    )
  })

  it('有隐形筛选 → 渲染提示条（否则条数少得像 bug）', async () => {
    routeQuery.value = { interface: 'POST /api/chat/{id}', status: 'error' }
    const w = await mountView({ items: [], total: 29 })
    const hint = w.find('.filter-hint')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('当前筛选')
    expect(hint.text()).toContain('POST /api/chat/{id}')
    expect(hint.text()).toContain('error')
  })

  it('提示条必须认领**三个**口径成因（窗口 / 去重 / 节点，缺一即是误导）', async () => {
    // 回归护栏：口径差异有三个独立成因，只写其中一两个会让用户觉得提示条在胡说。
    // ⚠️ 本条**只钉文案覆盖了三个维度**，不声称任何一维的量级 ——
    // 2026-09-18 曾据一个错误读数（status 未进 URL）写下「窗口是主因、差 60 倍」，已作废。
    routeQuery.value = { interface: 'POST /api/chat/{id}', status: 'error' }
    const w = await mountView({ items: [], total: 29 })
    const t = w.find('.filter-hint').text()
    expect(t).toContain('7 天')   // ① 时间窗（主因）
    expect(t).toContain('去重')    // ② 折叠
    expect(t).toContain('节点')    // ③ node=request 限定
    // 不许写死接口页的窗口值——用户可在接口页切 7d，写死必腐
    expect(t).not.toContain('接口页 24 小时')
  })

  it('URL 无筛选 → 不渲染提示条，也不传 interface/status（旧行为不变）', async () => {
    const w = await mountView({ items: [], total: 9 })
    expect(w.find('.filter-hint').exists()).toBe(false)
    const q = apiMock.listTraces.mock.calls[0][0]
    expect(q.status).toBeUndefined()
    expect(q.interface).toBeUndefined()
  })

  it('点「清除筛选」→ 清掉两者并重查（`status` 已有控件，但按钮叫「清除筛选」故一并清）', async () => {
    routeQuery.value = { interface: 'POST /api/chat/{id}', status: 'error' }
    const w = await mountView({ items: [], total: 29 })
    await w.find('.filter-hint button').trigger('click')
    await Promise.resolve(); await Promise.resolve()
    // 用 mock.lastCall（vitest 标准 API）而非 calls.at(-1)：本仓 tsconfig 的 lib 不含 es2022，
    // `.at()` 过不了 vue-tsc（曾把 npm run build 卡在类型检查这一步）。
    const last = apiMock.listTraces.mock.lastCall![0]
    expect(last.status).toBeUndefined()
    expect(last.interface).toBeUndefined()
  })
})

describe('状态控件（2026-09-20，P1-21 改判后）', () => {
  beforeEach(() => { apiMock.listTraces.mockReset(); push.mockReset(); routeQuery.value = {} })

  const stSel = (w: ReturnType<typeof mount>) =>
    w.findAll('select').filter(s => s.text().includes('全部状态'))[0]

  // ⚠️ **本组只证明「控件驱动了 listTraces」，证明不了「status 进了 URL」** ——
  //    api 模块被 mock，边界恰在这里（[[mock-boundary-hides-wiring-break]]）。
  //    「进 URL」那半边由 `api/traces.spec.ts` 的「真取 URL」用例承担，两半合起来才是完整证据链。
  it('选「仅错误」→ 重发请求，且 status=error 真的传给了 api 层', async () => {
    const w = await mountView({ items: [], total: 1949 })
    await stSel(w).setValue('error')
    await Promise.resolve(); await Promise.resolve()
    expect(apiMock.listTraces).toHaveBeenCalledTimes(2)
    expect(apiMock.listTraces.mock.lastCall![0].status).toBe('error')
  })

  it('切状态必须回第 1 页（与切窗同因：换了结果集，旧页码会越界）', async () => {
    const w = await mountView({ items: Array.from({ length: 20 }, (_, i) => row(i)), total: 100 })
    await w.find('.page-no').exists()            // 分页行在 ⇒ 确实能翻
    const next = nextBtn(w)!
    await next.trigger('click')
    await Promise.resolve(); await Promise.resolve()
    expect(apiMock.listTraces.mock.lastCall![0].page).toBe(2)
    await stSel(w).setValue('error')
    await Promise.resolve(); await Promise.resolve()
    expect(apiMock.listTraces.mock.lastCall![0].page).toBe(1)
  })

  it('选与当前相同的档 → 不重发（下拉 change 会抖，别白打一次请求）', async () => {
    const w = await mountView({ items: [], total: 9 })
    await stSel(w).setValue('')
    await Promise.resolve(); await Promise.resolve()
    expect(apiMock.listTraces).toHaveBeenCalledTimes(1)
  })

  it('URL 带 status 进来 → 下拉停在对应档，不是停在「全部状态」', async () => {
    routeQuery.value = { interface: 'POST /api/chat/{id}', status: 'error' }
    const w = await mountView({ items: [], total: 104 })
    expect((stSel(w).element as HTMLSelectElement).value).toBe('error')
  })
})
