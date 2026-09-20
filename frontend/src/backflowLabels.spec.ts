// backflowLabels.ts 单测：映射表值域完整性 + 未知值兜底 + reentryCaption 分支。
// 这些表的用途是「后端枚举 → 中文」，漏一个键的后果是界面直接显示英文/原始串，
// 而 TypeScript 无法在编译期检查运行时到达的字符串，故必须靠值域断言钉住。
import { describe, expect, it } from 'vitest'
import {
  CLUSTER_STATUS_LABEL, CONVERSION_ACTION_TEXT, INVALIDATE_REASON_NOTE,
  INPUT_TRUNCATED_WARN, LAYER_OPTIONS, OFFLINE_STATUS_TEXT, REVIEW_REASON_TEXT,
  STATUS_OPTIONS, VERIFY_STATUS_TEXT, WATCH_OPTIONS, conversionActionLabel,
  conversionDetailText, reentryCaption, taskState,
} from './backflowLabels'
import type { BackflowCluster } from './api/types'

// 后端写面的真实值域（自 backend/ 源码 grep 核对，2026-09-10）
const BACKEND_WRITTEN_ACTIONS = [
  'assemble', 'auto_fixed', 'claim', 'claim_ttl_expire', 'fixed_review', 'ignore',
  'invalidate', 'needs_review', 'needs_review_resolve', 'reentry', 'reopen', 'requeue',
]

// 真实样例取自 dev.obs conversion_record 实测（2026-09-18）：
// action 分布 claim 15/15 为 JSON，其余 5 种 action 0/15 全为纯文本。
const CLAIM_DETAIL =
  '{"fix_version": "0.2.1", "k": 2, "ttl_days": 14, "note": "sp 复核后确认是 error 分支"}'
const REGRESSION_DETAIL =
  'cluster=3881 link=2256 case_id=4084 run_id=3717 agent=smart-procurement@0.2.1 ' +
  'run_status=completed cases=1 dropped=0'

describe('conversionDetailText（P1-13）', () => {
  it('claim：JSON 原文 → 人话，不露出 fix_version/k/ttl_days 字段名', () => {
    const s = conversionDetailText('claim', CLAIM_DETAIL)
    expect(s).toBe('修复版本 0.2.1 · 连续通过阈值 K=2 · 复核窗 14 天 · 备注：sp 复核后确认是 error 分支')
    expect(s).not.toContain('fix_version')
    expect(s).not.toContain('{')
  })

  it('非 claim：原样透出（纯文本，含 regression_result 的 key=value）', () => {
    expect(conversionDetailText('regression_result', REGRESSION_DETAIL)).toBe(REGRESSION_DETAIL)
    expect(conversionDetailText('auto_fixed', 'K 序列 0.2.1→1.16.0 连续 2 次 pass'))
      .toBe('K 序列 0.2.1→1.16.0 连续 2 次 pass')
  })

  it('claim 但 detail 不是 JSON / 是空 / 是数组：一律回退原文，不白屏', () => {
    expect(conversionDetailText('claim', '历史遗留的纯文本备注')).toBe('历史遗留的纯文本备注')
    expect(conversionDetailText('claim', '')).toBe('')
    expect(conversionDetailText('claim', null)).toBe('')
    expect(conversionDetailText('claim', '"just a string"')).toBe('"just a string"')
    expect(conversionDetailText('claim', '[1,2]')).toBe('[1,2]')
  })

  it('claim 的 JSON 缺字段时不臆造：只渲染存在的那些', () => {
    expect(conversionDetailText('claim', '{"fix_version": "1.0.0"}')).toBe('修复版本 1.0.0')
    expect(conversionDetailText('claim', '{}')).toBe('{}')
  })
})

describe('CLUSTER_STATUS_LABEL', () => {
  it('覆盖后端 cluster_status 全部取值', () => {
    // models/error_flow.py ErrorCluster.status 枚举
    for (const s of ['open', 'claim', 'fixed', 'inactive', 'needs_review']) {
      expect(CLUSTER_STATUS_LABEL[s], s).toBeTruthy()
    }
  })

  it('与 STATUS_OPTIONS 下拉项一致（列表筛选不漏状态）', () => {
    const optValues = STATUS_OPTIONS.map(o => o.value).filter(Boolean).sort()
    expect(optValues).toEqual(Object.keys(CLUSTER_STATUS_LABEL).sort())
  })
})

describe('OFFLINE_STATUS_TEXT / VERIFY_STATUS_TEXT', () => {
  it('覆盖两种 status 的全部取值', () => {
    for (const s of ['assembled', 'draft', 'active', 'invalidated']) {
      expect(OFFLINE_STATUS_TEXT[s], s).toBeTruthy()
    }
    for (const s of ['pending', 'passed', 'failed', 'invalidated', 'superseded']) {
      expect(VERIFY_STATUS_TEXT[s], s).toBeTruthy()
    }
  })

  it('VERIFY_STATUS_TEXT 键集 == DDL link_verify_status 全 5 值（多/少键都要红）', () => {
    // 钉全等而非"包含"：此前只配 4 值、漏 invalidated，缺键在 UI 上兜底渲染英文裸值，
    // 而「包含式」断言抓不到缺失。值域自 backend/app/models/error_flow.py 枚举。
    expect(Object.keys(VERIFY_STATUS_TEXT).sort()).toEqual(
      ['failed', 'invalidated', 'passed', 'pending', 'superseded'])
  })

  it('WATCH_OPTIONS 的取值与 OFFLINE_STATUS_TEXT 一致（筛选下拉不漏态）', () => {
    const optValues = WATCH_OPTIONS.map(o => o.value).filter(Boolean).sort()
    expect(optValues).toEqual(Object.keys(OFFLINE_STATUS_TEXT).sort())
  })

  it('invalidated 文案含 §9.3 长句语义关键词（勿被简写覆盖）', () => {
    // detail §9.3 要求行内展示原文：含原因码、观察窗不再重生成、联系管理员三要素
    const t = OFFLINE_STATUS_TEXT.invalidated
    expect(t).toContain('invalidated')
    expect(t).toContain('窗口期内同键不再自动重生成')
    expect(t).toContain('平台管理员')
  })

  it('INVALIDATE_REASON_NOTE 覆盖 invalidate_reason 全部原因码', () => {
    for (const r of ['offline_cap_gap', 'online_content_gap', 'manual_invalidate']) {
      expect(INVALIDATE_REASON_NOTE[r], r).toBeTruthy()
    }
  })
})

describe('REVIEW_REASON_TEXT / LAYER_OPTIONS', () => {
  it('覆盖 needs_review_reason 全部取值', () => {
    for (const r of ['na', 'unclean_run', 'reentry_same_version', 'input_truncated']) {
      expect(REVIEW_REASON_TEXT[r], r).toBeTruthy()
    }
  })

  it('LAYER_OPTIONS 含 L1/L2 且首项为「全部」', () => {
    expect(LAYER_OPTIONS[0].value).toBe('')
    expect(LAYER_OPTIONS.map(o => o.value).filter(Boolean).sort()).toEqual(['L1', 'L2'])
  })

  it('INPUT_TRUNCATED_WARN 含 R-10 规则号（便于回溯 detail 条目）', () => {
    expect(INPUT_TRUNCATED_WARN).toContain('R-10')
    expect(INPUT_TRUNCATED_WARN).toContain('不计 K')
  })
})

describe('CONVERSION_ACTION_TEXT', () => {
  it('auto_activate 不在映射内（守卫：查实为 DDL 列注释举例，非设计值域）', () => {
    // solution_detail.md:642 的 `-- assemble/claim/ignore/fixed/reopen/requeue/auto_activate/
    // invalidate/…` 是列注释的**举例串**：全仓无任何语义定义章节，且同串里的 `fixed`
    // 与实现写面实际使用的 `fixed_review` 也对不上 → 它不是值域契约，故前端不配映射。
    // 保留这组断言的意义：若将来后端真落写点并补进 BACKEND_WRITTEN_ACTIONS，这里会红，
    // 提醒同步补映射——避免重演 D-3 那种「漏键 → 界面显示英文裸值」的缺陷形态。
    expect(CONVERSION_ACTION_TEXT.auto_activate).toBeUndefined()
    expect(BACKEND_WRITTEN_ACTIONS).not.toContain('auto_activate')
  })

  it('后端写过的 action 一个不漏（写面新增而前端漏配 → 界面显示英文）', () => {
    for (const a of BACKEND_WRITTEN_ACTIONS) {
      expect(CONVERSION_ACTION_TEXT[a], `后端写面 action 未配中文：${a}`).toBeTruthy()
    }
  })

  it('conversionActionLabel：未知 action 兜底显示原文，不显示 undefined', () => {
    expect(conversionActionLabel('claim')).toBe('认领')
    expect(conversionActionLabel('brand_new_action')).toBe('brand_new_action')
    expect(conversionActionLabel('')).toBe('')
  })
})

describe('reentryCaption', () => {
  // since_ts 在后端契约里是**非空 string**（types.ts:284），不是可空——勿按 null 写 fixture
  const base = {
    mode: 'claim' as const, count: 3, latest_version: '2026.09.10-r2',
    since_ts: '2026-09-01T00:00:00',
  }

  it('null 观察结果 → null（非 claim/fixed 态不渲染 caption）', () => {
    expect(reentryCaption(null)).toBeNull()
  })

  it('fixed 模式 count=0 → null（无复发不占版面）', () => {
    expect(reentryCaption({ ...base, mode: 'fixed', count: 0 })).toBeNull()
  })

  it('fixed 模式带版本：含版本号与「未过门控」解释', () => {
    const s = reentryCaption({ ...base, mode: 'fixed', count: 2 })!
    expect(s).toContain('<2026.09.10-r2>')
    expect(s).toContain('复发 2 次')
    expect(s).toContain('版本未过 reentry 门控未开新簇')
    expect(s).toContain('re-claim / reopen')
  })

  it('fixed 模式缺版本：不给空的尖括号', () => {
    const s = reentryCaption({ ...base, mode: 'fixed', count: 1, latest_version: null })!
    expect(s).not.toContain('<>')
    expect(s).toContain('同键新版本 复发 1 次')
  })

  it('claim 模式：自认领起计，带最新版本', () => {
    const s = reentryCaption(base)!
    expect(s).toContain('自认领起同键线上再现 3 次')
    expect(s).toContain('最新版本 <2026.09.10-r2>')
  })

  it('claim 模式缺版本：仍给出次数（不因缺版本整条不显示）', () => {
    const s = reentryCaption({ ...base, latest_version: null })!
    expect(s).toContain('自认领起同键线上再现 3 次')
    expect(s).not.toContain('最新版本')
  })
})

// ─── taskState（批 30：「现在轮谁」两条车道）────────────────────────────────
// 用户原话：「有的错误，我还没点确认，怎么 offline 那边就已经跑过 run，而且成功了？！」
// 根因 = 两条互不等待的车道并行，而页面上一个字都没写。本组用例穷尽 5 个簇状态 ×
// 关键 link 组合，并把「漏配新枚举」做成机械可检的（最后一条元测试）。
describe('taskState（批 30：两条车道）', () => {
  const link = (off: string, ver: string) => ({
    link_id: 1, payload_id: 'p', case_id: 'c', case_type: 'regression_error',
    offline_status: off, verify_status: ver, assembled_ts: null,
    invalidate_reason: null, requeue_count: 0,
  })
  const cl = (over: Partial<BackflowCluster> = {}): BackflowCluster =>
    ({
      cluster_id: 1, agent: 'a', interface: 'i', layer: 'L1', error_type: 'e',
      error_msg: null, input_hash: 'h', first_trace_id: null, input_truncated: 0,
      generation: 1, count: 1, status: 'open', first_ts: null, latest_ts: null,
      fix_version: null, claimed_by: null, claimed_at: null, claim_due_ts: null,
      claim_k: 2, needs_review_reason: null, link: null, ...over,
    }) as BackflowCluster

  it('open 无 link：等系统自动组装，同时也要你认领（两条车道并存）', () => {
    const r = taskState(cl())
    expect(r.short).toBe('等你认领')
    expect(r.mine).toBe(true)
    expect(r.auto).toContain('60 秒')   // 组装是 worker 周期扫描，不是实时
  })

  it('open + offline 已拉走：系统侧说进程，你侧仍要认领（**并行**，不是二选一）', () => {
    const r = taskState(cl({ link: link('active', 'pending') }))
    expect(r.auto).toContain('offline 拉走')
    expect(r.mine).toBe(true)           // ⚠️ 关键：系统在跑 ≠ 你没事干
    expect(r.short).toBe('等你认领')
  })

  it('open + payload 被驳回：说清是驳回、不是失败', () => {
    expect(taskState(cl({ link: link('invalidated', 'pending') })).auto).toContain('驳回')
  })

  it('open + 回归已 passed：明确「没有认领记录 ⇒ 系统不会自动收口」（用户报的那一幕）', () => {
    // 成因：offline 把**没人认领**的簇跑绿了，但 _apply_auto_fixed 要求 status='claim'
    // （claim.py:267 `.where(status == "claim")`）⇒ 它停在 open 不收口。
    // 当前库内尚不可达（open 的 link 全 pending），但因果上必然可达 ⇒ 必须能解释。
    const r = taskState(cl({ link: link('active', 'passed') }))
    expect(r.auto).toContain('没有认领记录')
    expect(r.short).toBe('等你认领')
  })

  it('claim + pending：系统在等回归，你无需操作（mine=false）', () => {
    const r = taskState(cl({ status: 'claim', link: link('active', 'pending'), claim_k: 3 }))
    expect(r.short).toBe('等 offline 回归')
    expect(r.mine).toBe(false)
    expect(r.auto).toContain('3 次')    // K 取 cluster.claim_k，不是写死的 2
  })

  it('claim + 通过一次：说清「还需连续 K 次」，不让人误以为已收口', () => {
    const r = taskState(cl({ status: 'claim', link: link('active', 'passed'), claim_k: 2 }))
    expect(r.auto).toContain('一次')
    expect(r.auto).toContain('2 次')
    expect(r.mine).toBe(false)
  })

  it('claim + failed：转人工（mine=true），且短句不写成「等 offline」', () => {
    const r = taskState(cl({ status: 'claim', link: link('active', 'failed') }))
    expect(r.mine).toBe(true)
    expect(r.short).toContain('处置')
  })

  it('needs_review：等你复核', () => {
    const r = taskState(cl({ status: 'needs_review' }))
    expect(r.mine).toBe(true)
    expect(r.short).toBe('等你复核')
  })

  it('fixed / inactive：已结束，均无需你操作', () => {
    for (const s of ['fixed', 'inactive']) {
      const r = taskState(cl({ status: s }))
      expect(r.mine).toBe(false)
      expect(r.human).toBe('无需操作')
    }
    expect(taskState(cl({ status: 'fixed' })).short).toBe('已收口')
  })

  it('未知 status：兜底中性短句 + 详情页带出原值（不裸渲染、不静默吞）', () => {
    const r = taskState(cl({ status: 'brand_new' }))
    expect(r.short).toBe('状态未识别')
    expect(r.auto).toContain('brand_new')
    expect(r.mine).toBe(false)
  })

  // ⚠️ 元测试：switch 漏配新枚举 → 本用例红。
  // 没有它，「后端加了状态值、前端走 default」只会在真机上表现为一句中性文案，无人会发现。
  // ⚠️ 本条是**真机取证抓到的**（#3858）：claim + payload 被驳回。
  // 第一版实现里 human 仍是「无需操作，等系统收口」—— 而 payload 已被驳回、
  // 推送已暂停，回归永远不会发生 ⇒ 让用户等一个不会来的结果。
  // 判别性：对第一版实现，下面的 mine / human 两条断言都会红。
  it('claim + payload 被驳回：必须转人工（K 序列已断，等不到自动收口）', () => {
    const r = taskState(cl({ status: 'claim', link: link('invalidated', 'pending') }))
    expect(r.mine).toBe(true)
    expect(r.short).toContain('处置')
    expect(r.human).not.toContain('无需操作')
    expect(r.auto).toContain('驳回')
  })

  it('claim + payload 尚未被拉走（assembled/draft）：确实无需操作，等系统', () => {
    for (const off of ['assembled', 'draft']) {
      const r = taskState(cl({ status: 'claim', link: link(off, 'pending') }))
      expect(r.mine, off).toBe(false)
      expect(r.human).toBe('无需操作，等系统收口')
    }
  })

  it('后端 cluster_status 全部取值都被 switch 显式覆盖（漏配即红）', () => {
    for (const s of Object.keys(CLUSTER_STATUS_LABEL)) {
      expect(taskState(cl({ status: s })).short).not.toBe('状态未识别')
    }
  })
})
