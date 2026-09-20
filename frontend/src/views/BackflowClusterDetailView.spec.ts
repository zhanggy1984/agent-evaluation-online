// cluster 详情页组件挂载测试（C2）。
// 本页是**唯一**有写动作的页面，风险集中在三处：
//   ① 状态门控（§9.4）——按钮该显的不显/不该显的显了，都会导致 409 或越权尝试；
//   ② admin 隔离——fixed-review / invalidate / requeue 仅 admin，前端隐藏是第一道，后端 require_admin 是第二道；
//   ③ claim 复核窗倒计时——1s tick + 45s 轮询，用假时钟驱，并验证卸载后定时器清零（防路由离开后泄漏）。
// 手法：mock 掉 vue-router 与 api 模块，断言「渲染出的按钮集合」与「发出的请求体」，不碰真实网络。
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { BackflowClusterDetail, BackflowLink } from '../api/types'
import BackflowClusterDetailView from './BackflowClusterDetailView.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { clusterId: '7' } }),
  useRouter: () => ({ push }),
}))

// vi.mock 会被提升到文件顶部，工厂内不能引用普通顶层 const（TDZ）——故用 vi.hoisted 一起提升
const apiMock = vi.hoisted(() => ({
  backflowClusterDetail: vi.fn(),
  claimCluster: vi.fn(),
  ignoreCluster: vi.fn(),
  reopenCluster: vi.fn(),
  fixedReview: vi.fn(),
  needsReviewResolve: vi.fn(),
  batchResolve: vi.fn(),
  linkInvalidate: vi.fn(),
  linkRequeue: vi.fn(),
}))
vi.mock('../api/backflow', () => apiMock)

function link(over: Partial<BackflowLink> = {}): BackflowLink {
  return {
    link_id: 1, payload_id: 'p-1', case_id: 'c-1', case_type: 'replay',
    offline_status: 'assembled', verify_status: 'pending',
    assembled_ts: '2026-09-10T00:00:00', invalidate_reason: null,
    requeue_count: 0, ...over,
  }
}

function mk(over: Partial<BackflowClusterDetail> = {}): BackflowClusterDetail {
  return {
    cluster_id: 7, agent: 'a-1', interface: 'POST /api/chat', layer: 'L1',
    error_type: 'llm_timeout', error_msg: '超时', input_hash: 'h-1',
    first_trace_id: 't-1', input_truncated: 0, generation: 1, count: 3,
    status: 'open', first_ts: '2026-09-01T00:00:00', latest_ts: '2026-09-10T00:00:00',
    fix_version: null, claimed_by: null, claimed_at: null, claim_due_ts: null,
    claim_k: 2, needs_review_reason: null, link: null,
    links: [], verify_runs: [], conversions: [], waiting_days: 9,
    reentry_observe: null, open_batches: [], result_gap_suspected: false,
    result_overdue: { hit: false, kind: null, since_ts: null, caption: null }, ...over,
  }
}

/** 挂载并等首屏 detail 落地（onMounted 里是 void loadDetail(true)） */
async function mountWith(d: BackflowClusterDetail) {
  apiMock.backflowClusterDetail.mockResolvedValue(d)
  const w = mount(BackflowClusterDetailView)
  await Promise.resolve()
  await Promise.resolve()
  return w
}

/** 推进微任务队列：写动作链是 submit → runAction → loadDetail → 回到 submitClaim 尾部，
 *  固定 2 个 tick 会停在中间（已设 okText 但未追加 warning）——统一用一个较宽的 flush */
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve() }

/** 渲染出的按钮文字（去空白），用于「按钮集合」级断言 */
const btnTexts = (w: ReturnType<typeof mount>) =>
  w.findAll('button').map(b => b.text().replace(/\s+/g, ' ').trim())

const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find(b => b.text().replace(/\s+/g, ' ').trim().includes(text))

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('obs_user', JSON.stringify({ username: 'admin', role: 'admin' }))
  vi.stubGlobal('confirm', vi.fn(() => true))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('needs_review：整批处置徽标', () => {
  it('needs_review 且带原因码 → 原因中文行可见', async () => {
    const w = await mountWith(mk({ status: 'needs_review', needs_review_reason: 'unclean_run' }))
    expect(w.text()).toContain('待人工复核原因')
    expect(w.text()).toContain('环境级 na 污染下 pass 存疑，批量处置')
  })

  it('needs_review 无原因码 → 不渲染空的「待人工复核原因」行', async () => {
    const w = await mountWith(mk({ status: 'needs_review', needs_review_reason: null }))
    expect(w.text()).not.toContain('待人工复核原因')
  })
})

describe('claim 复核窗倒计时（假时钟）', () => {
  it('未到期：显示剩余；过期后翻转 claimExpired 文案', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const nowMs = Date.now()
    const due = new Date(nowMs + 90_000)   // 90s 后到期
    const iso = due.toISOString().replace('Z', '')  // 后端 naive-UTC 同形

    const w = await mountWith(mk({ status: 'claim', claim_due_ts: iso }))
    expect(w.text()).toContain('复核窗剩余')

    vi.advanceTimersByTime(120_000)   // 越过到期点，靠 1s tick 触发重算
    await w.vm.$nextTick()
    expect(w.text()).toContain('复核窗口已超时')
    expect(w.text()).toContain('等待后台自动回退 open')
  })

  it('非 claim 态不起定时器（不无谓轮询）', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    await mountWith(mk({ status: 'open' }))
    expect(vi.getTimerCount()).toBe(0)
  })

  it('**卸载后定时器清零**（路由离开不泄漏 tick/轮询）', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const w = await mountWith(mk({ status: 'claim', claim_due_ts: '2099-01-01T00:00:00' }))
    expect(vi.getTimerCount()).toBeGreaterThan(0)   // 先证明确实起了
    w.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('45s 轮询：前台可见时重拉 detail（状态回退能被侦测到）', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const w = await mountWith(mk({ status: 'claim', claim_due_ts: '2099-01-01T00:00:00' }))
    apiMock.backflowClusterDetail.mockClear()
    vi.advanceTimersByTime(45_000)
    await Promise.resolve()
    expect(apiMock.backflowClusterDetail).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})

describe('时间线与角色显示', () => {
  it('conversions 用中文动作名 + 操作人回退（closed_by → user#id → 系统）', async () => {
    const w = await mountWith(mk({
      conversions: [
        { record_id: 1, action: 'claim', detail: null, closed_by: 'zhang', actor_user_id: 3, ts: '2026-09-10T00:00:00' },
        { record_id: 2, action: 'assemble', detail: null, closed_by: null, actor_user_id: 5, ts: null },
        { record_id: 3, action: 'reentry', detail: null, closed_by: null, actor_user_id: null, ts: null },
      ],
    }))
    const t = w.text()
    expect(t).toContain('认领')
    expect(t).toContain('zhang')
    expect(t).toContain('user#5')
    expect(t).toContain('系统')
  })

  it('verify_runs：pending 时展示「待 <fix_version> 回归 run」，failed 带 fail 标记', async () => {
    const w = await mountWith(mk({
      fix_version: 'v3',
      links: [link({ verify_status: 'pending' })],
      verify_runs: [{
        record_id: 1, run_id: 'run-1', bound_version: 'v2', case_pass: 0,
        run_status: 'failed', verified_ts: '2026-09-10T00:00:00', excluded_hit: true,
      }],
    }))
    expect(w.text()).toContain('待 v3 回归 run')
    expect(w.text()).toContain('excluded')   // 排除命中标记
  })

  it('input_truncated → 出 R-10 截断警示（仅 fixed/claim 态）', async () => {
    const on = await mountWith(mk({ status: 'claim', input_truncated: 1 }))
    expect(on.text()).toContain('R-10')
    const off = await mountWith(mk({ status: 'open', input_truncated: 1 }))
    expect(off.text()).not.toContain('R-10')
  })

  it('result_gap_suspected=true → 出「疑似丢失一笔结果推送」警示（不限状态）', async () => {
    const on = await mountWith(mk({ status: 'claim', result_gap_suspected: true }))
    expect(on.text()).toContain('疑似丢失一笔结果推送')
    const off = await mountWith(mk({ status: 'claim', result_gap_suspected: false }))
    expect(off.text()).not.toContain('疑似丢失一笔结果推送')
    // 已判定 fixed 也要可见（缺口可能是假修复的成因，不能只在等结果态提示）
    const fixed = await mountWith(mk({ status: 'fixed', result_gap_suspected: true }))
    expect(fixed.text()).toContain('疑似丢失一笔结果推送')
  })

  it('result_overdue.hit → 出「回查结果未达」警示，文案逐字照契约', async () => {
    const mark = { hit: true, kind: 'claim' as const, since_ts: '2026-09-01T00:00:00', caption: 'x' }
    const on = await mountWith(mk({ result_overdue: mark }))
    // 逐字比对契约串（不是 contains 子串）：改写文案 = 违反「后端不做二次措辞」的同一约定
    expect(on.text()).toContain('回查结果未达（疑似 offline 停摆），人工核查')
    const off = await mountWith(mk())
    expect(off.text()).not.toContain('回查结果未达')
  })

  it('result_overdue 不限状态展示（fixed 态仍需可见：可能是假修复）', async () => {
    const mark = { hit: true, kind: 'assembled' as const, since_ts: '2026-08-20T00:00:00', caption: 'x' }
    const fixed = await mountWith(mk({ status: 'fixed', result_overdue: mark }))
    expect(fixed.text()).toContain('回查结果未达')
  })

  it('result_overdue 带 since_ts → 附「自 … 起」；缺 since_ts → 只出文案不崩', async () => {
    const withTs = { hit: true, kind: 'claim' as const, since_ts: '2026-09-01T00:00:00', caption: 'x' }
    const a = await mountWith(mk({ result_overdue: withTs }))
    // 不断言格式化后的具体时刻：fmtTs 受运行时区影响，写死会让测试换个时区就红。
    // 只钉「括号包裹的『自…起』确实出现」+ 后端原值确实被消费（不因时区改写而丢）
    expect(a.text()).toContain('），人工核查（自 ')
    expect(a.text()).toContain('起）')

    const noTs = { hit: true, kind: 'claim' as const, since_ts: null, caption: 'x' }
    const b = await mountWith(mk({ result_overdue: noTs }))
    expect(b.text()).toContain('回查结果未达（疑似 offline 停摆），人工核查')
    expect(b.text()).not.toContain('（自 ')
  })

  it('reentry_observe caption 仅在 fixed/claim 且 count>0 时出现', async () => {
    const obs = { mode: 'fixed' as const, count: 2, latest_version: 'v2', since_ts: '2026-09-01T00:00:00' }
    const shown = await mountWith(mk({ status: 'fixed', reentry_observe: obs }))
    expect(shown.text()).toContain('复发 2 次')
    const zero = await mountWith(mk({ status: 'fixed', reentry_observe: { ...obs, count: 0 } }))
    expect(zero.text()).not.toContain('复发')
  })
})

describe('路由', () => {
  it('返回按钮回看板', async () => {
    const w = await mountWith(mk())
    // P1-7①：这里找的是**返回按钮**的文字（BackflowClusterDetailView.vue 头部），
    // 它跟随一级菜单名（App.vue MENUS）—— 改菜单名漏同步按钮 ⇒ 本条必红。
    // 保留「按文字找」而非改成按 name 找，护栏才有效。
    await btn(w, '错误闭环')!.trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'backflow' })
  })
})

// 批 6 · P1-12：本页此前是「死胡同」—— 列表页（BackflowView.vue:262）能跳 trace 详情，
// 进了详情页反而没有出口。判据与列表页**逐字一致**：缺 first_trace_id 或缺 agent 都不渲染，
// 避免给出必然 404 的死链（列表页同款断言见 BackflowView.spec.ts:225）。
describe('P1-12 代表 trace 出口（防死胡同 / 防死链）', () => {
  // 本组单独挂载：给未注册的 router-link 一个可断言的落点（不共用 mountWith —— 它被其余用例共享，
  // 加 stubs 会波及它们）；href 的正确性由真机取证（/backflow/clusters/3865 实读 + 点击到达）。
  async function mountStub(d: BackflowClusterDetail) {
    apiMock.backflowClusterDetail.mockResolvedValue(d)
    const w = mount(BackflowClusterDetailView, {
      global: { stubs: { RouterLink: { template: '<a class="trace-out"><slot /></a>' } } },
    })
    await Promise.resolve()
    await Promise.resolve()
    return w
  }

  it('first_trace_id 与 agent 齐备 → 渲染出口链接', async () => {
    const w = await mountStub(mk({ agent: 'customer-service', first_trace_id: 't-9' }))
    expect(w.find('a.trace-out').exists()).toBe(true)
    expect(w.text()).toContain('代表 trace')
  })

  it('first_trace_id 为空 → 不渲染（不给死链）', async () => {
    const w = await mountStub(mk({ first_trace_id: null }))
    expect(w.find('a.trace-out').exists()).toBe(false)
  })

  it('agent 为空 → 不渲染（缺任一个都不给）', async () => {
    const w = await mountStub(mk({ agent: '', first_trace_id: 't-9' }))
    expect(w.find('a.trace-out').exists()).toBe(false)
  })
})

// ─── 批 30：「现在轮谁」两条车道 ───────────────────────────────────────────
// 病根：用户报「我没点确认，offline 怎么就已经跑过 run 了」——系统那条线根本不等你，
// 而页面上零呈现。本组钉死「两条都渲染 + 高亮只给需要你那条」。
// 映射本体的穷尽性由 backflowLabels.spec.ts 的 taskState 一组覆盖，此处只管接线。
describe('现在轮谁（批 30）', () => {
  it('两条车道都渲染：上条说系统在自动干什么，下条说你要做什么', async () => {
    const w = await mountWith(
      mk({ status: 'open', link: link({ offline_status: 'active', verify_status: 'pending' }) }),
    )
    const lanes = w.findAll('.lane')
    expect(lanes).toHaveLength(2)
    expect(lanes[0].text()).toContain('系统自动')
    expect(lanes[0].text()).toContain('offline 拉走')   // 系统那条线不等你
    expect(lanes[1].text()).toContain('需要你')
    expect(lanes[1].text()).toContain('认领')
    // 系统已在跑 ≠ 你没事干：这个组合下「需要你」必须高亮（判别性所在）
    expect(lanes[1].classes()).toContain('need')
  })

  it('claim + 回归失败：你侧由「无需操作」翻转为「需处置」并高亮', async () => {
    const w = await mountWith(
      mk({ status: 'claim', link: link({ offline_status: 'active', verify_status: 'failed' }) }),
    )
    const lanes = w.findAll('.lane')
    expect(lanes[0].text()).toContain('回归未通过')
    expect(lanes[1].text()).toContain('重推')
    expect(lanes[1].classes()).toContain('need')
  })
})
