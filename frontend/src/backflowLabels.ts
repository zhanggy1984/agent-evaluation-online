// 回流看板文案集中（P2-6 T-3.7 / detail §9.3 逐字 + spec 未规定的状态中文自定）。
// 离线/回查状态字串 = detail §9.3 逐字（勿改字）；未知值兜底显示原文（防前端漂移漏展示）。
import type { BackflowCluster, ReentryObserve } from './api/types'

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
  // ⚠️ 批 37：批 36 此处的「online 侧不会自动重推」**当场被本次后端改动推翻** ——
  // worker assemble_job 内联的自动重推阶段已经会复活这类 link（requeue.py::auto_requeue_stuck）。
  // 与 §三十六 同一课：**改后端谓词/行为不会让任何前端文案测试变红**，只能靠人回读。
  online_content_gap: '现场需人工修正；online 侧会按上限自动重推（用尽后转人工）',
  manual_invalidate: '人工判无效',
}

// R-7 可愈性标注阈值（与后端 `SUSPECT_REQUEUE_THRESHOLD` 同值**不同物**）：
// 后端用它决定「自动重推停手」，前端用它在文案上转「需人工介入」。改其一要考虑另一。
export const SUSPECT_REQUEUE_THRESHOLD = 2

/**
 * invalidated 的两车道文案（批 37 抽出）：随**原因码 + 已重推次数**变化。
 * 抽出的理由 = 同一段判断要在 `open` / `claim` 两个分支各说一遍，
 * 写两处就迟早漂移（批 29「两处独立映射各自漂移」的教训）。
 */
function invalidatedText(c: BackflowCluster): { auto: string; human: string } {
  const reason = c.link?.invalidate_reason
  const n = c.link?.requeue_count ?? 0
  if (reason === 'offline_cap_gap') {
    // 能力缺口：恢复面在离线侧（补登记 agent/interface），online 重推无效（后端守卫同判）
    return {
      auto: 'payload 被 offline 驳回（能力缺口），online 侧不会自动重推',
      human: '恢复面在离线侧：补登记 agent/interface 后由离线侧自愈',
    }
  }
  if (reason !== 'online_content_gap') {
    // manual_invalidate / 未知原因：**不在这条自动出口的候选里**（后端 where 只收
    // online_content_gap）⇒ 不能顺着上一支说「系统会自动重推」
    return {
      auto: 'payload 被 offline 驳回（原因非内容缺口），系统不会自动重推',
      human: '需要人工介入：先确认驳回原因（详见上方原因码说明）',
    }
  }
  if (n >= SUSPECT_REQUEUE_THRESHOLD) {
    return {
      auto: `已自动重推 ${n} 次仍被驳回 —— 系统已停手`,
      human: '需要人工介入：查 offline 驳回的是哪一处内容缺口',
    }
  }
  return {
    auto: `payload 被 offline 驳回，系统会自动重推（已重推 ${n} 次）`,
    // 措辞回避「重推」二字：该词现在指**系统**动作，但它在页面上曾是「能点的按钮」
    // → 出现在 human（你侧）车道会让用户去找它（spec 的 BANNED 护栏同一理由）
    human: '在代码里修这一簇的 bug；若多次驳回仍不愈则需人工介入',
  }
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
  // 批 31：原「已让位（superseded）」——用户原话「太难理解了」。
  // **不删只改词**：`superseded` 有 4 个真实写入点（claim.py:158/255、batches.py:153、
  // verify.py:411-425），是**可达值**，现在显示 0 只因还没发生过；删掉后它第一次变 1、2、3 时
  // 那个数字会凭空消失（卡片总数对不上）。改词同样解决「看不懂」，且不丢信息。
  superseded: '已被新用例取代',
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
// offline 态筛选下拉（批 39：用户拍板「draft 删掉」）。
// ⚠️ **下拉只列「现在能筛出东西」的值**，不列「枚举里有」的值 —— 与 `STATUS_OPTIONS` 同一口径
// （见下方那条的判据），两处从此都**不等于**各自枚举的全键集，这是刻意的。
// 判据（2026-09-20 跨仓取证，含 offline 仓）：
//   assembled    写点 envelope.assemble_cluster / requeue.py:192 复位   库内 2 条  → 保留
//   active       offline ack（pull_loop.py:260 action="active"）        库内 14 条 → 保留
//   invalidated  offline ack（pull_loop.py:343 action="invalidated"）   库内 0 条  → **保留**
//   draft        **两侧都无有效写点**                                    库内 0 条  → 删除
// ⚠️ `invalidated` 库内 0 是**本批数据清理的结果**（批 39 删了 6 条走查数据），
//    不是它天然为 0 —— 拿这个 0 当「删选项」的依据，等于用自己刚制造的观测当判据。
//    它的写点在 offline 侧活着，随时会再产生，删了就真筛不出来。
// ⚠️ `draft` 与 `claim` **同类但死因不同**：claim 是**我方删了产生路径**（认领端点随批 35-B 撤除）；
//    draft 是**对端从未实现** —— online `_ACK_MATRIX`（ack.py:39）明写 `"draft": [("assembled", None)]`
//    是正常路径，但 offline `backflow_client.ack()` 全仓只有 2 个调用点（见上表），**无一发 draft**
//    ⇒ 契约写了、实现从未走 ⇒ 恒 0 是**必然的**，不是「停留时间短」。
// ⚠️ `OFFLINE_STATUS_TEXT` **不动**：短文案/taskState 是渲染真值的兜底，
//    万一库里出现 draft，页面照常渲染而非空白（同批 38 对 claim 的处置）。
export const WATCH_OPTIONS = [
  { value: '', label: '全部 offline 态' },
  { value: 'assembled', label: '待 offline 拉取' },
  { value: 'active', label: '已激活' },
  { value: 'invalidated', label: '已驳回（推送已停）' },
]

// 状态筛选下拉（批 38：用户拍板「三个都删，只留未处置/已修复」）。
// ⚠️ **下拉只列「现在能筛出东西」的值**，不列「枚举里有」的值 —— 两者从此不等，
// 这是刻意的（下方 spec 有专门的断言反向钉住）。
// 判据（2026-09-20 全仓 grep + 库内实测）：
//   open   写点 cluster.py:127 新建 / claim_ttl_job.py:69 TTL 回退  库内 7 条  → 保留
//   fixed  写点 claim.py:66 自动收口                                库内 10 条 → 保留
//   claim  **0 写点**（认领端点随批 35-B 撤除）⇒ 进不去了；但库内有 6 条真数据，
//          且 claim_ttl_job 的退回路径是活的（claim_due_ts 实测 2026-09-27~29）⇒
//          它是「正在消失的历史态」，不是空选项。仍被删出下拉：让用户筛一个
//          **不会再产生、且一周后自己消失**的值，成本大于收益。
//          ⚠️ 代价已与用户确认：那 6 条**暂时只能不加状态筛选地翻列表**（一周后自愈）。
//   inactive / needs_review  库内 0 条、全仓 0 写点（needs_review 由批 35-A 明确停用，
//          见 verify.py:337-347）⇒ 选中**必然空结果**且页面不解释。这是批 29 `L1/L2`
//          的同型缺陷，本次一并清掉。
// ⚠️ `CLUSTER_STATUS_LABEL` **不动**：徽标要照实渲染那 6 条历史 claim 簇，页面显示真值。
export const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'open', label: '未处置' },
  { value: 'fixed', label: '已修复' },
]

// 层（批 29 新手可读化）：原文只有「L1 / L2」两个字母，页面上无任何解释、
// 表里也无该列 ⇒ 用户选完了不知道自己筛了什么（实测 23/23 全 L1，选 L2 必空）。
// 语义取自后端 analyzer/classify.py:37（§2.5 L305-314）：
//   L1 = LLM 层错误透传 7 类；L2 = 兜底吸收/近 LLM 错误 4 类。
// ⚠️ 只延展 label 文案，**值域不动**（值仍是 L1/L2，后端 Literal 未变）。
export const LAYER_OPTIONS = [
  { value: '', label: '全部层' },
  { value: 'L1', label: 'L1 · LLM 层错误' },
  { value: 'L2', label: 'L2 · 兜底吸收（非 LLM 直接报错）' },
]

// ─── 新手可读化文案（2026-09-20 批 29：走查认定本组两页对新用户基本不可读）──────
// 设计取向：**能用「让信息可见」解决的，不靠「加解释」解决**（如补一列 offline 态 >
// 写一段话解释 watch 筛选）；文字只留给没有承载物的概念。
// ⚠️ 这些是**给用户看的**文案，不是代码注释。

/** 列表页页头一句话：这页是什么、现在该看哪。刻意短——不写成教程。 */
// ⚠️ 批 36：原句是「点进去认领 → 修复 → 由 offline 侧回归验证」——
// 批 35-B 撤除认领端点后，「点进去认领」是**页面上不存在的动作**。
export const BACKFLOW_INTRO =
  '线上失败的请求会自动聚成「错误簇」，一簇 = 同一类错误。本页按处置状态组织：' +
  '先看「未处置」的簇，点进去看它卡在哪 —— 本页只读，修 bug 在代码里做，' +
  '再由 offline 侧回归验证。'

/** 总览四卡的关系说明（批 39，用户报「四个数对不上」）。
 *
 *  排查结论：**四个数各自都是对的**，不是数据问题 —— 病根是四块用了两把尺子
 *  （卡①④ 数「簇」、卡②③ 数「评测用例」），而页面上一个字都没说。
 *  2026-09-20 实测：簇 23（open 7/claim 6/fixed 10）·用例 22（pending 12/passed 10）
 *  ·待修复集 4 ·待处置 13 —— ①与④对得上（7+6=13），②与③差 8 是因为③多要求
 *  `offline_status='active'`（12 里的另外 6 条已被 offline 驳回、2 条还没被拉走）。
 *
 *  ⚠️ 本条**写死了后端 overview 的口径**（谁是谁的子集、各自加了什么过滤）——
 *  backend/app/api/backflow.py::overview 改谓词时，**没有任何测试会因此变红**，
 *  只能靠人回读这一句。这是本写法的失效模式，与卡片上的「单位」徽标同生共死。 */
export const CARDS_NOTE =
  '上面四块数的是两种单位：「错误簇状态」「待处置」数的是簇，「回归验证结果」「待修复集」' +
  '数的是评测用例（一簇可含 0 条或多条，所以两边合计不相等是正常的）。' +
  '「待处置」=「错误簇状态」里还没修完的簇；「待修复集」=「回归验证结果」里 offline ' +
  '已拉走、还没回归通过的用例。'

/** 详情页页头一句话：这页有什么、从上往下怎么看。 */
// ⚠️ 批 36：原句含「与可执行动作」—— 批 35-B 后本页**已无任何处置动作**（只剩刷新），
// 那句话会让用户从上往下找按钮。
export const CLUSTER_INTRO =
  '这一簇错误的全貌：上面是它的现状（本页只读），下面依次是它在 offline 侧的评测用例（link）、' +
  '回归验证结果（run）、以及谁在什么时候动过它（流转记录）。'

/** 术语就地释义（就地小字用；每条 ≤14 字，避免页面变说明书）。 */
export const TERM = {
  cluster: '同一类错误的聚合',
  link: '本簇在 offline 侧的评测用例',
  inputHash: '入参指纹：相同则归为同一簇',
  fixVersion: '修复版本号。早期认领时填写',
  gen: '第几代簇（复发会开新簇）',
  claimK: '需连续通过几次回归才算修复',
  offlineStatus: '评测用例在 offline 侧的流转态',
} as const

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

// ─── 「现在轮谁」两条车道（2026-09-20 批 30）────────────────────────────────
// 病根（用户原话）：「有的错误，我还没点确认，怎么 offline 那边就已经跑过 run，而且成功了？！」
// 事实核查：属实且非 bug —— 每个簇上并行着**两条互不等待**的车道，而页面上一个字都没写：
//   🤖 系统：assemble_job 每 60s 自动扫 open 簇组装 payload（**不查认领**，assemble_job.py:19-22）
//            → offline 自己来拉（online 从不 push，pull.py:81）→ 跑回归 → ack 回填
//   👤 你  ：改代码修掉这个 bug → 下一次回归通过、K 满自动收口
//            （`_apply_auto_fixed`，claim.py:65 `.where(status == "open")`，
//             批 35-A 前该条件是 `claim` —— 见下方 open 分支的说明）
//   ⚠️ 批 35-B 后 online 侧**已无人工处置写面**（认领 / 重推 / 重开 / 复核端点全部撤除），
//      故本文件的 `human` 文案一律**不指向页面动作**，只说明「要在代码里改什么」。
// 实测佐证（dev.obs）：`open` 态里 6 条 link 已是 `active` —— 未经任何人认领，payload 已在 offline 手里。
//
// ⚠️ 为什么**一个 switch 产出三份文案**、而不是列表页/详情页各写一套映射：
// 批 29 的教训 —— 我按 `offline_status` 的映射去套 `verify_status` 的值，直到真机才暴露。
// 同一组状态有两处独立映射，就迟早各自漂移。此处 single source of truth。
//
// ⚠️ `mine` 由本函数显式给出、**不做「文案里有没有『等你』」的字符串匹配** ——
// 将来改文案不该悄悄改行为。
// ⚠️ 批 35-B 删掉了 `short`（原「现在轮谁」列的短句）：那一列已随需求①删除，
// 字段的唯一消费者随之消失，留着会读成「功能在、只是没数据」。
export interface TaskState {
  /** 详情页系统侧：系统正在自动做什么（无需你操作） */
  auto: string
  /** 详情页你侧：要你做什么 —— 批 35-B 后**不再有页面动作**，写的是要在仓库里改什么 */
  human: string
  /** 是否正等人动手（列表页「去处理 →」红字高亮用） */
  mine: boolean
}

export function taskState(c: BackflowCluster): TaskState {
  const link = c.link
  const ver = link?.verify_status
  const off = link?.offline_status
  switch (c.status) {
    case 'open': {
      // ⚠️ 批 35-A 把 `_apply_auto_fixed` 的准入由 `claim` 改成了 `open`
      // （claim.py:65）。旧文案「回归已通过——但本簇没有认领记录，系统不会自动收口」
      // 描述的正是**改之前**的行为，改完已成假话 ⇒ 本次一并订正。
      // 与 `claim` 分支同一条判据：**K 序列只要断了（被驳回）就必须转人工**，
      // 否则 auto 说「暂停推送」、human 说「等系统自动收口」，用户等一个不会来的结果。
      const stuck = off === 'invalidated'
      if (stuck) {
        // ⚠️ 批 37 订正：批 36 此处写「系统不会自动重试 —— 需要人工介入」，
        // 而本次后端已内联自动重推 ⇒ 那句话又成了假话（同一处的**第二次**翻转）。
        const t = invalidatedText(c)
        return { auto: t.auto, human: t.human, mine: true }
      }
      let auto: string
      if (ver === 'passed') auto = `回归已通过一次（需连续通过 ${c.claim_k} 次才自动收口）`
      else if (ver === 'failed') auto = '回归未通过，系统会自动重组装再跑一次'
      else if (off === 'active') auto = 'payload 已被 offline 拉走，正在跑回归'
      else if (off === 'draft') auto = 'payload 已生成，等 offline 确认用例'
      else if (off === 'assembled') auto = 'payload 已生成，等 offline 来拉'
      else auto = '还没生成 payload（系统每 60 秒扫一次，会自动补）'
      return {
        auto,
        human: `去修这一簇的 bug（在代码里改）—— 回归连续通过 ${c.claim_k} 次，系统自动收口`,
        mine: true,
      }
    }
    case 'claim': {
      const failed = ver === 'failed'
      // ⚠️ 真机取证（#3858，2026-09-20）抓到本函数第一版的一个自相矛盾：
      // `invalidated` 当时只改了 auto 文案，human 仍是「无需操作，等系统收口」——
      // 但 payload 已被驳回、推送已暂停 ⇒ 回归**永远不会发生**，
      // 用户会照这句话**等一个不会来的结果**（越像样的说明越容易被信）。
      // 判据收敛为一条：**K 序列只要断了（失败 / 被驳回）就必须转人工**。
      const stuck = failed || off === 'invalidated'
      if (off === 'invalidated') {
        // 驳回优先于 failed：payload 都没被受理，谈 K 序列无意义（与列表页同一判据）
        const t = invalidatedText(c)
        return { auto: t.auto, human: t.human, mine: true }
      }
      const auto = failed
        ? '回归未通过'
        : ver === 'passed'
          ? `回归通过一次（需连续通过 ${c.claim_k} 次才自动收口）`
          : `等待 offline 回归（需连续通过 ${c.claim_k} 次）`
      return {
        auto,
        // human 车道只说「你要做什么」，**不替系统编排日程** ——
        // 旧文案「重推 payload，或重开这一簇」两个动作都已随批 35-B 删除；
        // 而「系统会重组装再跑一次」在 claim 态并不成立（assemble_job 只扫 `open`，
        // 本态要先等 TTL 回退，claim_ttl_job 谓词 `claim_due_ts < now`）⇒ 不写。
        human: failed ? '去修这一簇的 bug（在代码里改）' : '无需操作，等系统收口',
        mine: stuck,     // 走到这里 stuck ⇔ failed（invalidated 已提前返回）
      }
    }
    case 'needs_review':
      // 批 35-B：`needs_review_resolve` 端点已撤除 ⇒ 旧文案「复核并决定这一簇怎么处置」
      // 指向一个页面上不存在的动作（假承诺）。
      return {
        auto: '系统无法自动判定，已转人工',
        human: '需要人工判定（online 侧已无处置入口）',
        mine: true,
      }
    case 'fixed':
      return {
        auto: '已修复收口，回归序列结束',
        human: '无需操作',
        mine: false,
      }
    case 'inactive':
      return { auto: '已忽略，不再跟踪', human: '无需操作', mine: false }
    default:
      // 兜底：DDL 的 cluster_status enum 只有上列 5 值、此处已穷尽，本分支不可达。
      // 真走到（后端加了新枚举）时：详情页带出原值供排查 —— 既不裸渲染枚举，也不静默吞掉。
      return {
        auto: `未识别的簇状态：${String(c.status)}`,
        human: '',
        mine: false,
      }
  }
}
