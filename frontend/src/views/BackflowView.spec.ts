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
  // 同 TracesView.spec：映射内容由真机验证覆盖，单测按恒等放行。
  agentDisplay: (n: string) => n,
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
  overview?: BackflowOverview
  // 注入口：错误必须在 mount 前装配好，不能 mount 后用 mockResolvedValue 覆盖
  // （覆盖会静默把 reject 变 resolve，造出「测失败路径但实际走成功路径」的假绿）
  overviewError?: unknown
  ifacesError?: unknown
}

async function mountView(opts: MountOpts = {}) {
  if (opts.overviewError !== undefined) apiMock.backflowOverview.mockRejectedValue(opts.overviewError)
  else apiMock.backflowOverview.mockResolvedValue(opts.overview ?? emptyOverview)
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

  // 批 33 删除两条用例（原「trace 链接点击 → 只跳 trace 详情一次（stopPropagation…）」
  // 与「first_trace_id 为空 → 不渲染 trace 按钮」）——它们钉的是**已删掉的「代表 trace」列**。
  // ⚠️ 是**删除而非改写成恒真**：留着会变成「实现没了、断言还在」的假绿。
  // 该跳转在详情页仍有出口，由 BackflowClusterDetailView.spec.ts 的 P1-12 一组覆盖。

  it('操作列：点击跳 cluster 详情，且**只跳一次**（@click.stop，不靠行冒泡兜底）', async () => {
    const w = await mountView({ items: [row({ cluster_id: 42 })] })
    await w.find('button.go').trigger('click')
    expect(push).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith({ name: 'backflow-cluster', params: { clusterId: 42 } })
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

  it('null 字段显示「-」而非 undefined / 1970（后端空值不外泄）', async () => {
    // 批 33：本条原名「时间戳 null → 显示「-」而非 1970」——它钉的是**已删的「首现/最新」列**。
    // 改成钉**全表**：任一行不得出现 `undefined` / `null` / `1970` 这三种空值外泄形态。
    // ⚠️ 这比原断言**更宽**：原断言只覆盖时间列，改后覆盖每一格。
    const w = await mountView({
      items: [row({ first_ts: null, latest_ts: null, fix_version: null, error_msg: null, link: null })],
    })
    const t = w.find('tbody tr').text()
    expect(t).not.toContain('undefined')
    expect(t).not.toContain('null')
    expect(t).not.toContain('1970')
    expect(t).toContain('-')   // fix_version 空 / 无 link 各出一处
  })

  it('批 33：删掉的三列不再渲染（入参指纹 / 代表 trace / 首现·最新）', async () => {
    const w = await mountView({
      items: [row({ input_hash: 'd'.repeat(64), first_trace_id: 'task-649', first_ts: '2026-09-16T18:30:03' })],
    })
    const t = w.text()
    // 判别性：这三个值都真实存在于数据里，若列还在必然渲染出来
    expect(t).not.toContain('d'.repeat(64))
    expect(t).not.toContain('task-649')
    expect(t).not.toContain('2026-09-16')
    // 表头也不得残留（防「列空了但表头还在」）
    const heads = w.findAll('thead th').map(h => h.text())
    expect(heads.some(h => h.includes('入参指纹'))).toBe(false)
    expect(heads.some(h => h.includes('代表 trace'))).toBe(false)
    expect(heads.some(h => h.includes('首现'))).toBe(false)
    expect(heads.some(h => h.includes('操作'))).toBe(true)
  })

  // 批 39（用户提出）：文案**恒为「查看 →」**。批 35-B 后 online 侧已无任何处置动作，
  // 「去处理」是承诺一个点不出来的东西（批 36 抓到的同一类病）。
  // ⚠️ 但高亮**仍随 mine 翻转** —— 它表达「这簇还等着人在代码里修」，不是「点它去操作」。
  // 判别性：把文案改回三元式即红；把 `:class` 里的 need 去掉也红（两个不变量各钉一头）。
  it('操作列：文案恒为「查看 →」；高亮仍随 mine 翻转（两个不变量分开钉）', async () => {
    const w = await mountView({
      items: [row({ cluster_id: 1, status: 'open' }), row({ cluster_id: 2, status: 'fixed' })],
    })
    const gos = w.findAll('td button.go')
    expect(gos).toHaveLength(2)
    expect(gos[0].text()).toBe('查看 →')
    expect(gos[1].text()).toBe('查看 →')
    expect(gos[0].classes()).toContain('need')       // open 态 = 还没修完 ⇒ 红字
    expect(gos[1].classes()).not.toContain('need')
    expect(w.text()).not.toContain('去处理')
  })

  // ─── 批 39：四卡「单位 + 关系」（用户报「四个数对不上」）─────────────────────
  // 排查结论：四个数各自都对，病根是四块用了两把尺子（簇 / 评测用例）且页面零提示。
  // ⚠️ 本组**证不了**「文案与后端谓词一致」—— 那段一致性靠人回读
  // backend/app/api/backflow.py::overview，见 CARDS_NOTE 上方注释。
  const overview4 = {
    clusters: { open: 7, claim: 6, fixed: 10 }, to_fix: 4,
    by_agent: [{ agent: 'contract-check', open: 7, claim: 1 }],
    links: { pending: 12, passed: 10, failed: 0, invalidated: 0, superseded: 0 },
  } as unknown as BackflowOverview

  it('四卡各带「单位」徽标（卡①④ = 簇，卡②③ = 用例）', async () => {
    const w = await mountView({ overview: overview4 })
    expect(w.findAll('.card .unit').map(u => u.text())).toEqual(['簇', '用例', '用例', '簇'])
  })

  it('卡片区上方渲染关系说明，且两种单位都被点到', async () => {
    const w = await mountView({ overview: overview4 })
    const note = w.find('.cards-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('簇')
    expect(note.text()).toContain('评测用例')
    // 不渲染 Markdown 星号：模板里误写 `**` 会原样显示（批 34 踩过）
    expect(note.text()).not.toContain('**')
  })

  it('两处过期小字已订正（「已推给 offline」说大了 / 「还没人认领」指向已删动作）', async () => {
    const w = await mountView({ overview: overview4 })
    const cards = w.findAll('.card').map(c => c.text())
    expect(cards[2]).toContain('offline 已拉走')   // 待修复集：谓词是 active，不是 assembled
    expect(cards[3]).toContain('未处置')           // 待处置：改说状态，不说动作
    expect(cards[3]).toContain('复核中')
    expect(w.text()).not.toContain('还没人认领')
  })

  it('二期入口在本页零渲染（detail §9.1：弃留墙/quality 不从本页引）', async () => {
    const w = await mountView({ items: [row()] })
    expect(w.text()).not.toContain('弃留墙')
    expect(w.text().toLowerCase()).not.toContain('quality')
  })

  // ⚠️ 批 29 改判：本用例原来是「现行 link 摘要：取 items[0].link 的 offline 语义」——
  // 它**把一处误导当规格钉住了**：页脚那句读起来像全页/全局的值，实际只取表格第一行，
  // 而 `api/types.ts:237` 明写「list 侧**每个 cluster 一个**」link。
  // 现改为断言「每行各自的值」：**两行给不同 offline_status，必须同时渲染出两个标签**。
  // 判别性：旧实现只渲染 items[0] 的一个 → 本条对它必红（这正是它该有的样子）。
  const mkLink = (id: number, s: string) => ({
    link_id: id, payload_id: `p${id}`, case_id: `c${id}`, case_type: 'replay',
    offline_status: s, verify_status: 'pending',
    assembled_ts: null, invalidate_reason: null, requeue_count: 0,
  })

  it('offline 态列 = 每行各自的值（两行不同则都要出现；旧的 items[0] 冒充全局会红）', async () => {
    const w = await mountView({
      items: [row({ link: mkLink(1, 'assembled') }), row({ link: mkLink(2, 'invalidated') })],
    })
    const t = w.text()
    expect(t).toContain('待 offline 拉取') // assembled
    expect(t).toContain('已驳回（推送已停）') // invalidated（批 36：原「重推位」指向已撤除的重推动作）
    expect(t).not.toContain('现行 link')   // 页脚那句误导已删
  })

  it('行无 link ⇒ 该格显示 `-`，不渲染空标签、不抛错', async () => {
    const w = await mountView({ items: [row({ link: null })] })
    expect(w.findAll('tbody tr').length).toBe(1)
  })

  // ⚠️ 本条**是我真机当场抓到的那个错**：概览「回归验证结果」卡的键是 **verify_status**
  // （后端 backflow.py:457-462 `group_by(ErrorCaseLink.verify_status)`，值域
  // pending/passed/failed/invalidated/superseded），**不是 offline_status**。
  // 我第一版拿 offline 的映射去套 ⇒ 只有 `invalidated` 撞上，其余全兜底成裸键，
  // 真机读数 = `pending14 / passed8 / failed0 / …` —— 一眼可见。
  // 本用例把「必须是中文、不得出现裸键」钉死，正是为了让那种错在单测阶段就红。
  it('回归验证结果卡渲染中文（键是 verify_status，拿 offline 映射去套会退化成裸键）', async () => {
    const w = await mountView({
      overview: {
        clusters: {}, to_fix: 0, by_agent: [],
        links: { pending: 14, passed: 8, failed: 0, invalidated: 1, superseded: 0 },
      } as unknown as BackflowOverview,
    })
    const card = w.findAll('.card')[1]
    const t = card.text()
    expect(t).toContain('待回归')
    expect(t).toContain('回归通过')
    expect(t).toContain('已失效')   // invalidated
    expect(t).not.toContain('pending')
    expect(t).not.toContain('passed')
  })

  // 批 29：`verify_status='invalidated'` 是**不可达值**（全仓零写入点，取证见 BackflowView.vue
  // 的 verifyRows 注释）⇒ 恒 0 时不该占一行版位；**但值 >0 时必须照常显示**。
  // 上面那条用的正是 invalidated: 1 —— 两条合起来钉死「只隐藏 0，不隐藏真值」，
  // 所以将来后端落了写入点也不会出现「真值被前端静默吞掉」。
  it('superseded 保留（可达值）、恒 0 的不可达态「已失效」不占位', async () => {
    const w = await mountView({
      overview: {
        clusters: {}, to_fix: 0, by_agent: [],
        links: { pending: 3, passed: 1, failed: 0, invalidated: 0, superseded: 0 },
      } as unknown as BackflowOverview,
    })
    const t = w.findAll('.card')[1].text()
    expect(t).toContain('待回归')
    expect(t).toContain('已被新用例取代')  // superseded 可达，恒 0 也留着（批 31 改词，未删）
    expect(t).not.toContain('已失效')  // invalidated 不可达且为 0 ⇒ 不占位
  })

  // 批 35-B（需求①）：删「现在轮谁」列（批 30 引入）。原两条用例随列删除 ——
  // 「等你认领」在写面撤除后已是**假承诺**（online 侧没有认领这个动作了），不是回归。
  it('「现在轮谁」列已删除：表头不含该列，行内无 .wheel', async () => {
    const w = await mountView({ items: [row({ cluster_id: 1, status: 'open' })] })
    expect(w.text()).not.toContain('现在轮谁')
    expect(w.findAll('td .wheel')).toHaveLength(0)
  })
})
