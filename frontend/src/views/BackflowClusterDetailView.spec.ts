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
    assembled_ts: '2026-09-10T00:00:00', invalidate_reason: null, ...over,
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
    reentry_observe: null, open_batches: [], ...over,
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

describe('状态门控（§9.4 按钮集合）', () => {
  // 表驱动：每种状态的「应有按钮」与「绝不该出现的按钮」
  const cases: {
    status: string
    admin: boolean
    want: string[]
    forbid: string[]
  }[] = [
    {
      status: 'open', admin: true,
      want: ['认领并复核', '忽略'],
      forbid: ['重开', '通过复核', '驳回', 'escalated', '处置整批', '失效', '重推'],
    },
    {
      // admin 复核动作（D-1 修复后可达：曾因 canIgnore 抢先命中而成为死分支）
      status: 'claim', admin: true,
      want: ['通过复核', '驳回', '忽略'],
      forbid: ['认领并复核', '重开（回到未处置）', 'escalated'],
    },
    {
      // **viewer 在 claim 态不得见复核动作**——这是 admin 隔离的核心断言
      status: 'claim', admin: false,
      want: ['忽略'],
      forbid: ['通过复核', '驳回', '认领并复核'],
    },
    {
      status: 'fixed', admin: true,
      want: ['重开'],
      forbid: ['认领并复核', '忽略（复核中', '通过复核'],
    },
    { status: 'inactive', admin: false, want: ['重开'], forbid: ['认领并复核'] },
    {
      status: 'needs_review', admin: false,
      want: ['重开（回到未处置）', 'escalated（仅记录）'],
      forbid: ['认领并复核', '通过复核'],
    },
  ]

  for (const c of cases) {
    it(`${c.status}${c.admin ? '/admin' : '/viewer'}：应见 [${c.want.join('、')}]`, async () => {
      localStorage.setItem('obs_user', JSON.stringify({
        username: 'u', role: c.admin ? 'admin' : 'viewer',
      }))
      const w = await mountWith(mk({ status: c.status }))
      const texts = btnTexts(w)
      for (const t of c.want) expect(texts.some(x => x.includes(t)), `缺 ${t}`).toBe(true)
      for (const t of c.forbid) expect(texts.some(x => x.includes(t)), `不该有 ${t}`).toBe(false)
    })
  }

  it('claim/admin 点「通过复核」→ fixedReview(id, true)；点「驳回」→ false', async () => {
    apiMock.fixedReview.mockResolvedValue({ cluster_id: 7, status: 'fixed' })
    const w = await mountWith(mk({ status: 'claim' }))
    await btn(w, '通过复核')!.trigger('click')
    await flush()
    expect(apiMock.fixedReview).toHaveBeenCalledWith(7, true)

    await btn(w, '驳回')!.trigger('click')
    await flush()
    expect(apiMock.fixedReview).toHaveBeenCalledWith(7, false)
  })

  it('claim/admin 点「忽略（先回退）」→ ignoreCluster（与 viewer 同语义）', async () => {
    apiMock.ignoreCluster.mockResolvedValue({ cluster_id: 7, status: 'claim' })
    const w = await mountWith(mk({ status: 'claim' }))
    await btn(w, '忽略（先回退）')!.trigger('click')
    await flush()
    expect(apiMock.ignoreCluster).toHaveBeenCalledWith(7)
  })

  it('未知状态（后端新增枚举）→ 不渲染任何处置按钮，而非渲染错按钮', async () => {
    const w = await mountWith(mk({ status: 'brand_new' }))
    expect(w.findAll('.ops').length).toBe(0)
    expect(w.text()).toContain('brand_new')   // 状态原文兜底展示
  })
})

describe('needs_review：整批处置徽标', () => {
  it('无 open_batches → 不渲染「处置整批」', async () => {
    const w = await mountWith(mk({ status: 'needs_review' }))
    expect(btnTexts(w).some(t => t.includes('处置整批'))).toBe(false)
  })

  it('有 open_batches → 渲染且带 batch_id/run_id/ref_count', async () => {
    const w = await mountWith(mk({
      status: 'needs_review',
      open_batches: [{
        batch_id: 9, run_id: 'run-x', agent: 'a-1',
        bound_version: 'v2', error_type: 'llm_timeout', ref_count: 4,
      }],
    }))
    const b = btn(w, '处置整批')!
    expect(b.text()).toContain('batch#9')
    expect(b.text()).toContain('run-x')
    expect(b.text()).toContain('4 link')

    await b.trigger('click')
    await Promise.resolve()
    expect(apiMock.batchResolve).toHaveBeenCalledWith(9, 'reopen_cluster')
  })

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

describe('link 行内 admin 动作门控', () => {
  it('viewer：assembled link 不渲染「失效」', async () => {
    localStorage.setItem('obs_user', JSON.stringify({ username: 'u', role: 'viewer' }))
    const w = await mountWith(mk({ links: [link({ offline_status: 'assembled' })] }))
    expect(btnTexts(w)).not.toContain('失效')
  })

  it('admin：assembled/draft 可失效，active/invalidated 不可', async () => {
    const w = await mountWith(mk({
      links: [
        link({ link_id: 1, offline_status: 'assembled' }),
        link({ link_id: 2, offline_status: 'draft' }),
        link({ link_id: 3, offline_status: 'active' }),
        link({ link_id: 4, offline_status: 'invalidated' }),
      ],
    }))
    // 4 行只有前两行各有一个「失效」
    expect(btnTexts(w).filter(t => t === '失效')).toHaveLength(2)
  })

  it('admin：重推仅 invalidated∧verify pending∧cluster∈{open,claim,needs_review}', async () => {
    const bad = await mountWith(mk({
      status: 'fixed',  // 状态不符
      links: [link({ offline_status: 'invalidated', verify_status: 'pending' })],
    }))
    expect(btnTexts(bad)).not.toContain('重推')

    const bad2 = await mountWith(mk({
      status: 'open',
      links: [link({ offline_status: 'invalidated', verify_status: 'passed' })],  // verify 不符
    }))
    expect(btnTexts(bad2)).not.toContain('重推')

    const good = await mountWith(mk({
      status: 'open',
      links: [link({ offline_status: 'invalidated', verify_status: 'pending' })],
    }))
    expect(btnTexts(good)).toContain('重推')
    await btn(good, '重推')!.trigger('click')
    await Promise.resolve()
    expect(apiMock.linkRequeue).toHaveBeenCalledWith(1)
  })

  it('失效点击：确认后调 linkInvalidate(link_id, null)', async () => {
    const w = await mountWith(mk({ links: [link({ link_id: 42, offline_status: 'draft' })] }))
    await btn(w, '失效')!.trigger('click')
    await Promise.resolve()
    expect(apiMock.linkInvalidate).toHaveBeenCalledWith(42, null)
  })

  it('cancel 确认框 → 不发请求', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    const w = await mountWith(mk({ links: [link({ link_id: 42, offline_status: 'draft' })] }))
    await btn(w, '失效')!.trigger('click')
    await Promise.resolve()
    expect(apiMock.linkInvalidate).not.toHaveBeenCalled()
  })
})

describe('认领表单：请求体形状', () => {
  it('默认 K=2，空备注归一为 null', async () => {
    apiMock.claimCluster.mockResolvedValue({
      cluster_id: 7, fix_version: 'v9', claim_k: 2,
      claim_due_ts: '2026-09-24T00:00:00', warning: null,
    })
    const w = await mountWith(mk({ status: 'open' }))
    await btn(w, '认领并复核')!.trigger('click')

    await w.find('input[placeholder^="fix_version"]').setValue('  v9  ')  // 前后空白须 trim
    await w.find('form.claim-form').trigger('submit')
    await Promise.resolve()

    expect(apiMock.claimCluster).toHaveBeenCalledWith(7, {
      fix_version: 'v9', k: 2, note: null,
    })
  })

  it('K 选 1 → 请求体 k=1（下拉非默认分支）', async () => {
    apiMock.claimCluster.mockResolvedValue({
      cluster_id: 7, fix_version: 'v1', claim_k: 1,
      claim_due_ts: '2026-09-24T00:00:00', warning: null,
    })
    const w = await mountWith(mk({ status: 'open' }))
    await btn(w, '认领并复核')!.trigger('click')
    await w.find('input[placeholder^="fix_version"]').setValue('v1')
    await w.find('select.sel').setValue('1')
    await w.find('input[placeholder^="备注"]').setValue('已定位')
    await w.find('form.claim-form').trigger('submit')
    await Promise.resolve()
    expect(apiMock.claimCluster).toHaveBeenCalledWith(7, {
      fix_version: 'v1', k: 1, note: '已定位',
    })
  })

  it('fix_version 空 → 不发请求 + 报必填（前端先拦，不打后端）', async () => {
    const w = await mountWith(mk({ status: 'open' }))
    await btn(w, '认领并复核')!.trigger('click')
    await w.find('input[placeholder^="fix_version"]').setValue('   ')
    await w.find('form.claim-form').trigger('submit')
    await Promise.resolve()
    expect(apiMock.claimCluster).not.toHaveBeenCalled()
    expect(w.text()).toContain('fix_version 必填')
  })

  it('表单初值取现 cluster 的 fix_version/claim_k（修复中重认领不丢上下文）', async () => {
    const w = await mountWith(mk({ status: 'open', fix_version: 'v-old', claim_k: 1 }))
    await btn(w, '认领并复核')!.trigger('click')
    expect((w.find('input[placeholder^="fix_version"]').element as HTMLInputElement).value)
      .toBe('v-old')
    expect((w.find('select.sel').element as HTMLSelectElement).value).toBe('1')
  })
})

describe('写动作失败路径', () => {
  it('409 ERR_CLUSTER_0002 → 提示并发处置并重拉 detail', async () => {
    const { ApiError } = await import('../api/client')
    apiMock.claimCluster.mockRejectedValue(new ApiError(409, 'ERR_CLUSTER_0002', '并发处置'))
    const w = await mountWith(mk({ status: 'open' }))
    apiMock.backflowClusterDetail.mockClear()

    await btn(w, '认领并复核')!.trigger('click')
    await w.find('input[placeholder^="fix_version"]').setValue('v1')
    await w.find('form.claim-form').trigger('submit')
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve()

    expect(w.text()).toContain('ERR_CLUSTER_0002')
    expect(w.text()).toContain('已被并发处置')
    expect(apiMock.backflowClusterDetail).toHaveBeenCalledTimes(1)  // runAction 内重拉
  })

  // D-2 修复后：成功文案在前、后端软提示追加在后，两段都不丢
  it('claim 返回 warning（R-5/R-7 软提示）→ 与成功文案合并展示', async () => {
    apiMock.claimCluster.mockResolvedValue({
      cluster_id: 7, fix_version: 'v1', claim_k: 3, claim_due_ts: 'x',
      warning: 'K 由 2 自动升为 3（历史复发）',
    })
    const w = await mountWith(mk({ status: 'open' }))
    await btn(w, '认领并复核')!.trigger('click')
    await w.find('input[placeholder^="fix_version"]').setValue('v1')
    await w.find('form.claim-form').trigger('submit')
    await flush()
    expect(w.text()).toContain('已认领（K=2），复核窗开启')
    expect(w.text()).toContain('K 由 2 自动升为 3')
  })

  it('claim 无 warning → 只出成功文案，不留悬空分号', async () => {
    apiMock.claimCluster.mockResolvedValue({
      cluster_id: 7, fix_version: 'v1', claim_k: 2, claim_due_ts: 'x', warning: null,
    })
    const w = await mountWith(mk({ status: 'open' }))
    await btn(w, '认领并复核')!.trigger('click')
    await w.find('input[placeholder^="fix_version"]').setValue('v1')
    await w.find('form.claim-form').trigger('submit')
    await flush()
    expect(w.find('.ok-text').text()).toBe('已认领（K=2），复核窗开启')
  })

  it('加载失败 → 错误文案 + 不渲染详情区', async () => {
    const { ApiError } = await import('../api/client')
    apiMock.backflowClusterDetail.mockRejectedValue(new ApiError(404, 'ERR_CLUSTER_0001', '不存在'))
    const w = mount(BackflowClusterDetailView)
    await Promise.resolve(); await Promise.resolve()
    expect(w.text()).toContain('ERR_CLUSTER_0001')
    expect(w.text()).toContain('该 cluster 不存在或已删除')
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
    await btn(w, '回流看板')!.trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'backflow' })
  })
})
