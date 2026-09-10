// backflowLabels.ts 单测：映射表值域完整性 + 未知值兜底 + reentryCaption 分支。
// 这些表的用途是「后端枚举 → 中文」，漏一个键的后果是界面直接显示英文/原始串，
// 而 TypeScript 无法在编译期检查运行时到达的字符串，故必须靠值域断言钉住。
import { describe, expect, it } from 'vitest'
import {
  CLUSTER_STATUS_LABEL, CONVERSION_ACTION_TEXT, INVALIDATE_REASON_NOTE,
  INPUT_TRUNCATED_WARN, LAYER_OPTIONS, OFFLINE_STATUS_TEXT, REVIEW_REASON_TEXT,
  STATUS_OPTIONS, VERIFY_STATUS_TEXT, WATCH_OPTIONS, conversionActionLabel, reentryCaption,
} from './backflowLabels'

// 后端写面的真实值域（自 backend/ 源码 grep 核对，2026-09-10）
const BACKEND_WRITTEN_ACTIONS = [
  'assemble', 'auto_fixed', 'claim', 'claim_ttl_expire', 'fixed_review', 'ignore',
  'invalidate', 'needs_review', 'needs_review_resolve', 'reentry', 'reopen', 'requeue',
]

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
