// 回流看板文案集中（P2-6 T-3.7 / detail §9.3 逐字 + spec 未规定的状态中文自定）。
// 离线/回查状态字串 = detail §9.3 逐字（勿改字）；未知值兜底显示原文（防前端漂移漏展示）。
import type { ReentryObserve } from './api/types'

// cluster 状态中文（spec 未规定，实现自定）
export const CLUSTER_STATUS_LABEL: Record<string, string> = {
  open: '未处置',
  claim: '复核中',
  fixed: '已修复',
  inactive: '已忽略',
  needs_review: '待人工复核',
}

// offline_status 逐字（detail §9.3）：invalidated 长句含原因码语义，行内展示原文
export const OFFLINE_STATUS_TEXT: Record<string, string> = {
  assembled: '已生成（待 offline 拉取）',
  draft: '已生成用例（待 offline 确认）',
  invalidated:
    '结构自检失败（invalidated）——本错误仍在观察：窗口期内同键不再自动重生成；offline 能力补齐/修正现场后可重推；长期停留请联系平台管理员',
  active: '已激活（offline）',
}

// invalidated 原因码 → 恢复路径提示（置于 invalidated 长句下方）
export const INVALIDATE_REASON_NOTE: Record<string, string> = {
  offline_cap_gap: '能力补齐后自动恢复',
  online_content_gap: '现场已修正，待 admin 重推',
  manual_invalidate: '人工判无效',
}

// verify_status → 文案（pending 的「待 <fix_version> 回归 run」需 fix_version 上下文，见视图拼接）。
// 值域 = DDL link_verify_status 全 5 值：补齐 invalidated——它全仓零写入点、当下不可达，
// 但缺键会兜底渲染英文原文（种子 e2e_seed 覆盖到后实测为裸值 `invalidated`），
// 与同列其余 4 值的中文不一致；补全成本一行，漏掉则埋一个将来写点落地才暴露的 UI 缺口。
export const VERIFY_STATUS_TEXT: Record<string, string> = {
  pending: '待回归',
  passed: '回归通过',
  failed: '回归失败',
  invalidated: '已失效（invalidated）',
  superseded: '已让位（superseded）',
}

// needs_review_reason → 处置语义（detail §9.3 逐字）
export const REVIEW_REASON_TEXT: Record<string, string> = {
  na: '该 case infra 无法判定，cluster 级单点处置',
  unclean_run: '环境级 na 污染下 pass 存疑，批量处置',
  reentry_same_version: '同版本旧 run pass，需人工/升版',
  input_truncated: '复现输入截断证据不可信，需人工复核或小输入重测',
}

// conversion action → 中文（未知 action 兜底原文；枚举随 claim.py 写面收敛）
// 刻意不配 auto_activate：solution_detail.md:642 那串是 DDL 列注释的**举例**、不是值域契约——
// 它无任何语义定义章节，且同串里的 `fixed` 与实现写面实际用的 `fixed_review` 也对不上。
// 配了反而会让后人误以为存在一份正式「设计枚举」。将来后端真落写点时，
// spec 的守卫断言会红（见 backflowLabels.spec.ts），届时再补不迟。
export const CONVERSION_ACTION_TEXT: Record<string, string> = {
  assemble: '组装',
  claim: '认领',
  ignore: '忽略',
  reopen: '重开',
  requeue: '重推',
  invalidate: '人工失效',
  auto_fixed: '回归收敛自动置 fixed',
  fixed_review: 'admin 复核',
  reentry: '同键复发重开',
  claim_ttl_expire: '复核窗超时回退',
  needs_review: '转待复核',
  needs_review_resolve: '待复核处置',
}

export function conversionActionLabel(action: string): string {
  return CONVERSION_ACTION_TEXT[action] ?? action
}

// conversion detail → 可读文本（P1-13）。claim 的 detail 是**认领表单的 JSON 原文**
// （backend/app/backflow/claim.py:141 写入 {fix_version,k,ttl_days,note}），原样显示会
// 露出 fix_version/k/ttl_days 这些内部字段名。实测该 action **15/15 为 JSON**，
// 其余 action **0/15**（regression_result/assemble/auto_fixed/config_change/requeue
// 都是纯文本），故只对 claim 做结构化。
// **解析失败一律回退原文**：后端改格式时退化成改前行为，不白屏、不吞信息。
export function conversionDetailText(action: string, detail: string | null): string {
  if (action !== 'claim' || !detail) return detail ?? ''
  let o: unknown
  try {
    o = JSON.parse(detail)
  } catch {
    return detail
  }
  if (!o || typeof o !== 'object' || Array.isArray(o)) return detail
  const m = o as Record<string, unknown>
  const parts: string[] = []
  if (m.fix_version) parts.push(`修复版本 ${String(m.fix_version)}`)
  // k = claim_k：k_seq ≥ claim_k 才判 passed（verify.py decide_k），即需连续通过的 run 数
  if (m.k !== undefined && m.k !== null) parts.push(`连续通过阈值 K=${String(m.k)}`)
  if (m.ttl_days !== undefined && m.ttl_days !== null) parts.push(`复核窗 ${String(m.ttl_days)} 天`)
  if (m.note) parts.push(`备注：${String(m.note)}`)
  return parts.length > 0 ? parts.join(' · ') : detail
}

// watch 筛选选项（值 = 后端 watch 参数；'' = 全部）
export const WATCH_OPTIONS = [
  { value: '', label: '全部 offline 态' },
  { value: 'assembled', label: '待 offline 拉取' },
  { value: 'draft', label: '待 offline 确认' },
  { value: 'active', label: '已激活' },
  { value: 'invalidated', label: '已驳回（重推位）' },
]

export const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'open', label: '未处置' },
  { value: 'claim', label: '复核中' },
  { value: 'fixed', label: '已修复' },
  { value: 'inactive', label: '已忽略' },
  { value: 'needs_review', label: '待人工复核' },
]

export const LAYER_OPTIONS = [
  { value: '', label: '全部层' },
  { value: 'L1', label: 'L1' },
  { value: 'L2', label: 'L2' },
]

// 疑似丢推送警示（详情页 result_gap_suspected=true 时展示）。措辞与后端 GAP_CAPTION 同义：
// 一句「可能少了一笔结果」即可，**不做对账面板**（§8.7 只要求可观测标记）。
export const RESULT_GAP_WARN =
  '疑似丢失一笔结果推送（回归 K 序列已中断，待 offline 补推或人工核查）'

// 「回查结果未达」提示（详情页 result_overdue.hit=true 时展示，F-18）。
// **逐字照契约**（`solution_detail.md` v1.23 #7 与后端 `OVERDUE_CAPTION` 同串）：
// 「前端命中即原样渲染，后端不做二次措辞」——此处**不得改写**（与上面 GAP 那条的
// 「同义即可」不同规，别照抄 GAP 的处置）。
export const RESULT_OVERDUE_WARN = '回查结果未达（疑似 offline 停摆），人工核查'

// input_truncated 警示（claim/fixed 态展示；R-10，detail §9.3）
export const INPUT_TRUNCATED_WARN =
  '复现输入原始 input>8K 已截断，证据不完整：相关 run pass 不计 K；建议小输入重测或人工复核（R-10）'

// blocked/claim 同键复发观察 caption（P2-6 新增钉定措辞；purge 保留窗内现算）
export function reentryCaption(o: ReentryObserve | null): string | null {
  if (!o) return null
  if (o.mode === 'fixed') {
    if (o.count === 0) return null
    const ver = o.latest_version ? ` <${o.latest_version}>` : ''
    return `同键新版本${ver} 复发 ${o.count} 次（judge 保留窗内现算；版本未过 reentry 门控未开新簇）；若非属本 fix 请 re-claim / reopen`
  }
  const ver = o.latest_version ? `，最新版本 <${o.latest_version}>` : ''
  return `自认领起同键线上再现 ${o.count} 次（已计入观察计数）${ver}`
}
