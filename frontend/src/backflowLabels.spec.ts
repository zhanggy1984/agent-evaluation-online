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
import type { BackflowCluster, BackflowLink } from './api/types'

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

  // ⚠️ 批 38 本条**反向重写**：原断言是「下拉项 == 标签表键集（不漏状态）」，
  // 前提是「枚举里的值都能筛」。该前提在批 35-B/35-A 之后**已不成立** ——
  // claim/inactive/needs_review 三个值都没有写点了，选中必然空结果。
  // 现在钉的是相反的不变量：**下拉只列活值，且徽标仍照实覆盖全部 5 值**。
  // 判别性：有人把死值加回下拉（或把标签表裁成只剩活值）即红。
  it('下拉只列活值；徽标仍覆盖全部枚举值（两者刻意不等）', () => {
    const optValues = STATUS_OPTIONS.map(o => o.value).filter(Boolean).sort()
    expect(optValues).toEqual(['fixed', 'open'])
    // 三个死值必须**不在**下拉里
    for (const dead of ['claim', 'inactive', 'needs_review']) {
      expect(optValues, dead).not.toContain(dead)
      // 但标签必须还在 —— 库内 6 条历史 claim 簇要照实渲染徽标
      expect(CLUSTER_STATUS_LABEL[dead], dead).toBeTruthy()
    }
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
  const link = (off: string, ver: string, over: Partial<BackflowLink> = {}) => ({
    link_id: 1, payload_id: 'p', case_id: 'c', case_type: 'regression_error',
    offline_status: off, verify_status: ver, assembled_ts: null,
    invalidate_reason: null, requeue_count: 0, ...over,
  })
  const cl = (over: Partial<BackflowCluster> = {}): BackflowCluster =>
    ({
      cluster_id: 1, agent: 'a', interface: 'i', layer: 'L1', error_type: 'e',
      error_msg: null, input_hash: 'h', first_trace_id: null, input_truncated: 0,
      generation: 1, count: 1, status: 'open', first_ts: null, latest_ts: null,
      fix_version: null, claimed_by: null, claimed_at: null, claim_due_ts: null,
      claim_k: 2, needs_review_reason: null, link: null, ...over,
    }) as BackflowCluster

  // 批 35-B：以下断言原为「列表页短句 `short`」，该字段随「现在轮谁」列一并删除
  // ⇒ 判据改挂到 `human` / `auto` 上，判别力不变（同一个 switch 产出）。
  it('open 无 link：等系统自动组装，同时也要你修（两条车道并存）', () => {
    const r = taskState(cl())
    expect(r.human).toContain('代码里改')
    expect(r.mine).toBe(true)
    expect(r.auto).toContain('60 秒')   // 组装是 worker 周期扫描，不是实时
  })

  it('open + offline 已拉走：系统侧说进程，你侧仍要修（**并行**，不是二选一）', () => {
    const r = taskState(cl({ link: link('active', 'pending') }))
    expect(r.auto).toContain('offline 拉走')
    expect(r.mine).toBe(true)           // ⚠️ 关键：系统在跑 ≠ 你没事干
    expect(r.human).toContain('代码里改')
  })

  it('open + payload 被驳回：说清是驳回、不是失败', () => {
    expect(taskState(cl({ link: link('invalidated', 'pending') })).auto).toContain('驳回')
  })

  it('open + payload 被驳回：human **不得**承诺自动收口（推送已停，回归不会发生）', () => {
    // 与 claim 分支同一条判据（K 序列断了 ⇒ 必须转人工）。
    // 判别性：`open` 分支若照抄通用文案「…系统自动收口」，本条即红 —— 那正是
    // 批 30 在 claim 分支犯过的错（auto 说暂停、human 说等系统，用户等一个不会来的结果）。
    const r = taskState(cl({ link: link('invalidated', 'pending') }))
    expect(r.human).not.toContain('自动收口')
    expect(r.human).toContain('人工介入')
  })

  // 批 37：后端内联自动重推（requeue.py::auto_requeue_stuck）⇒ invalidated 的文案
  // 必须**按原因码 + 已重推次数**分叉。批 36 那句「系统不会自动重试」本次当场变假。
  // ⚠️ 这一族测试测的是「我写的串还在不在」，不是「这句话对后端还成不成立」——
  // 后端改谓词不会让它们变红，只能靠改后端的人回读（§三十六的教训）。
  it('invalidated + online_content_gap 且未达上限：说会自动重推（不承诺一定成功）', () => {
    const r = taskState(cl({
      link: link('invalidated', 'pending',
        { invalidate_reason: 'online_content_gap', requeue_count: 0 }),
    }))
    expect(r.auto).toContain('会自动重推')
    expect(r.auto).toContain('0 次')
    expect(r.auto).not.toContain('不会')   // 旧假话的判别性断言
  })

  it('invalidated + 已达上限：说清系统已停手、转人工', () => {
    const r = taskState(cl({
      link: link('invalidated', 'pending',
        { invalidate_reason: 'online_content_gap', requeue_count: 2 }),
    }))
    expect(r.auto).toContain('已停手')
    expect(r.auto).toContain('2 次')
    expect(r.human).toContain('人工介入')
  })

  it('invalidated + 非内容缺口原因：不得顺着上一支说会重推（它不在候选里）', () => {
    for (const reason of ['offline_cap_gap', 'manual_invalidate']) {
      const r = taskState(cl({
        link: link('invalidated', 'pending', { invalidate_reason: reason }),
      }))
      // ⚠️ 不能写 not.toContain('会自动重推') —— '不会自动重推' 是它的**超串**，
      // 那样写恒红（本次实测踩到）；否定式断言必须连否定词一起写死。
      expect(r.auto, reason).toContain('不会自动重推')
    }
  })

  it('claim + online_content_gap 驳回：与 open 分支同一套文案（抽一处不漂移）', () => {
    const lk = link('invalidated', 'pending', { invalidate_reason: 'online_content_gap' })
    expect(taskState(cl({ status: 'claim', link: lk })).auto)
      .toBe(taskState(cl({ link: lk })).auto)
  })

  it('open + 回归已 passed：说清还需连续 K 次（批 35-A 后 K 满**会**自动收口）', () => {
    // ⚠️ 本条被订正过：旧断言是「明确『没有认领记录 ⇒ 系统不会自动收口』」，
    // 描述的是 `_apply_auto_fixed` 准入还是 `claim` 时的行为。批 35-A 把准入改成
    // `open`（claim.py:65）后，open 簇 K 满**会**收口 ⇒ 旧文案已成假话，断言随之改写。
    const r = taskState(cl({ link: link('active', 'passed'), claim_k: 3 }))
    expect(r.auto).toContain('3 次')
    expect(r.auto).toContain('自动收口')
  })

  it('claim + pending：系统在等回归，你无需操作（mine=false）', () => {
    const r = taskState(cl({ status: 'claim', link: link('active', 'pending'), claim_k: 3 }))
    expect(r.human).toBe('无需操作，等系统收口')
    expect(r.mine).toBe(false)
    expect(r.auto).toContain('3 次')    // K 取 cluster.claim_k，不是写死的 2
  })

  it('claim + 通过一次：说清「还需连续 K 次」，不让人误以为已收口', () => {
    const r = taskState(cl({ status: 'claim', link: link('active', 'passed'), claim_k: 2 }))
    expect(r.auto).toContain('一次')
    expect(r.auto).toContain('2 次')
    expect(r.mine).toBe(false)
  })

  it('claim + failed：转人工（mine=true），且 human 指向代码、不是「等 offline」', () => {
    const r = taskState(cl({ status: 'claim', link: link('active', 'failed') }))
    expect(r.mine).toBe(true)
    expect(r.human).toContain('代码里改')
    expect(r.human).not.toContain('等系统')
  })

  it('needs_review：转人工，但不指向已撤除的「复核」动作', () => {
    const r = taskState(cl({ status: 'needs_review' }))
    expect(r.mine).toBe(true)
    expect(r.human).toContain('人工判定')
  })

  it('fixed / inactive：已结束，均无需你操作', () => {
    for (const s of ['fixed', 'inactive']) {
      const r = taskState(cl({ status: s }))
      expect(r.mine).toBe(false)
      expect(r.human).toBe('无需操作')
    }
  })

  it('未知 status：auto 带出原值（不裸渲染、不静默吞）', () => {
    const r = taskState(cl({ status: 'brand_new' }))
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
      expect(taskState(cl({ status: s })).auto).not.toContain('未识别')
    }
  })

  // ⚠️ 需求③的回归护栏：批 35-B 撤除了 online 侧**全部**人工处置写面
  // （认领 / 重推 / 重开 / 复核 9 个端点）。文案若还提这些动作，就是在教用户
  // 点一个不存在的按钮 —— 而这类假承诺**不会让任何测试变红**，只会在真机上把人卡住。
  // 判别性：把任一分支的 human 改回「认领这一簇，填写修复版本」即红。
  it('human 不得提及已撤除的页面动作（认领/重推/重开/复核）', () => {
    const BANNED = ['认领', '重推', '重开', '复核']
    const states = [
      cl(), cl({ link: link('active', 'pending') }), cl({ link: link('invalidated', 'pending') }),
      cl({ link: link('active', 'passed') }), cl({ link: link('active', 'failed') }),
      cl({ status: 'claim', link: link('active', 'pending') }),
      cl({ status: 'claim', link: link('active', 'failed') }),
      cl({ status: 'claim', link: link('invalidated', 'pending') }),
      cl({ status: 'needs_review' }), cl({ status: 'fixed' }), cl({ status: 'inactive' }),
    ]
    for (const c of states) {
      for (const word of BANNED) {
        expect(taskState(c).human, `${c.status}/${word}`).not.toContain(word)
      }
    }
  })
})
