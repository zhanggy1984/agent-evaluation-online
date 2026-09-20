<script setup lang="ts">
// cluster 详情页（P2-6 T-3.7 / detail §9.2 独立路由 backflow-cluster）：元数据 + links 表 +
// verify_runs 版本×pass/fail 时间线 + conversions 审计时间线。
// ⚠️ 批 35-B：**本页只读**。人工处置动作区（认领/忽略/重开/通过复核/驳回/单条与整批复核/
// link 失效与重推）连同按钮整块删除 —— 后端端点同期撤除，留着按钮只会点出 404。
// 簇的收口全自动：assemble_job 每 60s 组装推送 → offline 拉取执行 → 回推 run → K 满自动 fixed。
// claim 复核窗（1s tick + 45s 轮询）**展示面保留**：历史 claim 行仍可能处于复核窗内。
// 时间戳 = 后端 _iso naive-UTC 字符串 → fmtISO / parseISODate。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { backflowClusterDetail } from '../api/backflow'
import { ApiError } from '../api/client'
import type { BackflowClusterDetail, BackflowLink } from '../api/types'
import {
  CLUSTER_INTRO,
  CLUSTER_STATUS_LABEL,
  conversionActionLabel,
  conversionDetailText,
  INVALIDATE_REASON_NOTE,
  INPUT_TRUNCATED_WARN,
  OFFLINE_STATUS_TEXT,
  reentryCaption,
  RESULT_GAP_WARN,
  taskState,
  RESULT_OVERDUE_WARN,
  REVIEW_REASON_TEXT,
  TERM,
  VERIFY_STATUS_TEXT,
} from '../backflowLabels'
import { agentDisplay, useAgents } from '../composables/useAgents'
import { fmtISO } from '../format'

const route = useRoute()
const router = useRouter()
const clusterId = Number(route.params.clusterId)

const detail = ref<BackflowClusterDetail | null>(null)
const loading = ref(true)
const errorMsg = ref('')

// 批 41：claim 复核窗**倒计时展示面已删**（含「认领人」）—— 认领/复核端点随批 35-B 撤除，
// 页面上已无任何可做的人工动作，倒计时读起来像「你有 N 天去复核」，实际无人能复核。
// ⚠️ 但 **45s 轮询保留**：后端 `claim_ttl_job`（worker，每 60s 扫全表）会把超窗的 claim
// 自动回退 `open` 并写一条 `claim_ttl_expire` 流转记录。无轮询则本页会一直停在「复核中」
// 而不反映这个系统动作 —— 那正是批 30 记过的「系统背着我干了什么」。
let pollId: number | undefined

const isClaim = computed(() => detail.value?.status === 'claim')

const st = computed(() => detail.value?.status ?? '')
const stLabel = computed(() => CLUSTER_STATUS_LABEL[st.value] ?? st.value)
// 「现在轮谁」两条车道（批 30）：detail 未加载时为 null，模板已在 v-if="detail" 内使用。
// 映射本体在 backflowLabels.taskState —— 与列表页同源，勿在此另写一套。
const lanes = computed(() => (detail.value ? taskState(detail.value) : null))

function statusCls(s: string): string {
  return `st-${s}`
}

function fmtTs(v: string | null | undefined): string {
  return fmtISO(v)
}

// 「待人工复核原因」展示用：needs_review 现只可能来自历史数据（处置面已删，进了没人能救出去）。
const needsReview = computed(() => st.value === 'needs_review')

function showObserveCaption(): boolean {
  const o = detail.value?.reentry_observe
  return !!o && o.count > 0
}

function reentryText(): string | null {
  return reentryCaption(detail.value?.reentry_observe ?? null)
}

function offlineLabel(s: string): string {
  return OFFLINE_STATUS_TEXT[s] ?? s
}

// ⚠️ 批 50（#33）注明：三元里的「待 {fix_version} 回归 run」分支**当前不可达** ——
// `fix_version` 已零写点且存量已于批 42 清空（详见 backflowLabels.ts 同名注释），
// 取值恒为 null ⇒ 实际恒走 '待回归'。**保留本分支是为了「值若回来还能显示」**，
// 不是「这里有两条路可走」；照它去构造用例会验到一条不存在的路。
function verifyLabel(lk: BackflowLink): string {
  if (lk.verify_status === 'pending') {
    return detail.value?.fix_version ? `待 ${detail.value.fix_version} 回归 run` : '待回归'
  }
  return VERIFY_STATUS_TEXT[lk.verify_status] ?? lk.verify_status
}

function reasonText(): string {
  const r = detail.value?.needs_review_reason
  return r ? (REVIEW_REASON_TEXT[r] ?? r) : ''
}

function actorName(c: { closed_by: string | null; actor_user_id: number | null }): string {
  return c.closed_by || (c.actor_user_id != null ? `user#${c.actor_user_id}` : '系统')
}

async function loadDetail(showSpinner = true): Promise<void> {
  if (showSpinner) loading.value = true
  errorMsg.value = ''
  try {
    detail.value = await backflowClusterDetail(clusterId)
    syncClaimTimers()
  } catch (e) {
    if (e instanceof ApiError) {
      errorMsg.value = `加载失败（${e.code}）：${e.message}`
      detail.value = null
    } else {
      throw e
    }
  } finally {
    if (showSpinner) loading.value = false
  }
}

function back(): void {
  void router.push({ name: 'backflow' })
}

// claim 期 45s 后台轮询（仅前台可见时拉，防后台堆积）—— 承接后端自动回退（见上）
function syncClaimTimers(): void {
  if (isClaim.value) {
    if (pollId === undefined) {
      pollId = window.setInterval(() => {
        if (document.visibilityState === 'visible') void loadDetail(false)
      }, 45000)
    }
  } else {
    stopClaimTimers()
  }
}

function stopClaimTimers(): void {
  if (pollId !== undefined) { window.clearInterval(pollId); pollId = undefined }
}

watch(isClaim, (v) => { if (v) syncClaimTimers(); else stopClaimTimers() })
// 同 TraceDetailView：本页无 agent 下拉，需自己触发一次 displayMap 加载（单例内短路重复拉）。
onMounted(() => { void loadDetail(true); void useAgents().load() })
onUnmounted(() => stopClaimTimers())

const rows = computed(() => detail.value?.conversions ?? [])
// 批 31：「流转记录」占详情页 **68% 的文字**（真机实测 1097 字 / 24 处术语），
// 第一屏被审计流水淹没 —— 用户报「整页看不懂」，主因是这一块，不是哪句话写得不好。
// 顺序 = ts 倒序（真机核对 #3881：13:57 → 13:34）⇒ 取前 N 条即「最近 N 条」。
const CONV_PREVIEW = 3
const showAllConv = ref(false)
const convRows = computed(() =>
  showAllConv.value ? rows.value : rows.value.slice(0, CONV_PREVIEW),
)
</script>

<template>
  <div>
    <header class="bar">
      <!-- P1-7①：按钮文字跟随一级菜单名（App.vue MENUS）——菜单改了这里必须同步 -->
      <button class="btn-ghost" type="button" @click="back">← 错误闭环</button>
      <strong class="title">
        错误簇 <span class="mono">#{{ clusterId }}</span>
        <span class="muted" v-if="detail">· {{ agentDisplay(detail.agent) }}{{ detail.interface ? `.${detail.interface}` : '' }}</span>
        <!-- P1-12：本页原为「死胡同」—— 列表页（BackflowView.vue:262）能跳 trace 详情，
             进了详情页反而没有出口。判据与列表页逐字一致（缺 trace_id 或缺 agent 不渲染，
             不给死链），目标路由 /traces/:agent/:traceId 早已存在。 -->
        <router-link
          v-if="detail?.first_trace_id && detail.agent" class="link-like"
          :to="{ name: 'trace-detail', params: { agent: detail.agent, traceId: detail.first_trace_id } }"
        >代表 trace ↗</router-link>
      </strong>
      <button class="btn-ghost" type="button" :disabled="loading" @click="loadDetail(true)">刷新</button>
    </header>

    <!-- 页头一句话（批 29）：此前进页只有一行 `cluster #123` + 一排裸字段
         （gen1 / 计数 23 / claim_k 2 …），新用户不知道这一页在讲什么、该从哪读起。 -->
    <p class="intro">{{ CLUSTER_INTRO }}</p>
    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <template v-if="!loading && detail">
      <!-- 「现在轮谁」两条车道（批 30）：本页最该早看到的一句话。
           **两行并列是刻意的** —— 上一条线（系统自动）根本不等你，下一条线才是你要做的；
           只给一句「等 offline 回归」会让人以为那期间自己没事干，而事实是两条线并行。
           ⚠️ 批 38（用户提出）：**「需要你」行改为条件渲染** —— `mine=false` 的簇（已修复 /
           已忽略 / 等系统收口）那行只会写「无需操作」，是纯噪音。
           **但不整块删掉**：`open` 态那行是页面上**唯一**说明「得有人去改代码」的地方 ——
           簇变 fixed 只有一条路（offline 回推回归连续通过 K 次），而回归过不过取决于那个
           bug 有没有被改。删了它页面就只剩「系统会自动…」，正是批 30 的病根
           （用户等一个不会来的结果）。 -->
      <section class="lanes">
        <div class="lane">
          <span class="lane-tag">系统自动</span>
          <span class="lane-text">{{ lanes?.auto }}</span>
        </div>
        <div v-if="lanes?.mine" class="lane need">
          <span class="lane-tag">需要你</span>
          <span class="lane-text">{{ lanes?.human }}</span>
        </div>
      </section>

      <!-- 头部元信息 -->
      <section class="panel meta">
        <div class="meta-row">
          <span class="status" :class="statusCls(detail.status)">{{ stLabel }}</span>
          <span class="tag-mono">{{ detail.layer }}</span>
          <strong>{{ detail.error_type }}</strong>
          <span class="muted">{{ detail.error_msg }}</span>
        </div>
        <!-- 批 29：此行原为 `gen1 / 计数 23 / fix - / claim_k 2 / input_hash xxx` 裸字段并列，
             五个词新用户一个都读不懂（gen 是缩写、fix 是半截词）。改为**白话标签 + 值**，
             正式术语降为 title（想查的人仍查得到，不再要求新手先 hover 才知道是什么）。 -->
        <div class="meta-row muted small">
          <span :title="TERM.gen">第 {{ detail.generation }} 代</span>
          <span title="本簇累计发生的次数">发生 {{ detail.count }} 次</span>
          <!-- 批 42：原「修复版本 {x} / 未填写」已删 —— 该字段已零生成入口（认领端点随批 35-B
               撤除、offline 侧也无填写处），留着只会渲染一个永远不再变、也无人能改的值。
               ⚠️ 保留下方「待 {fix_version} 回归 run」的 link 文案：它把值当**上下文**用，
               删了退化成「待回归」，信息更少。 -->
          <!-- 批 40：K 进度。`seq` 为 null = 不适用（无现行 link / 非 pending / 无 case_id），
               此时退回只报阈值 —— 显示「0/2」会把「还没轮到」误读成「一次都没通过」。 -->
          <span v-if="typeof detail.seq === 'number'" :title="TERM.claimK">
            回归已连续通过 {{ detail.seq }}/{{ detail.claim_k }} 次
          </span>
          <span v-else :title="TERM.claimK">回归阈值 K={{ detail.claim_k }}</span>
          <span :title="TERM.inputHash">入参指纹 <span class="mono">{{ detail.input_hash }}</span></span>
        </div>
        <div class="meta-row muted small">
          <span>已等待 {{ detail.waiting_days }} 天</span>
          <!-- 批 41：原「认领人 {{ claimed_by }}（时间）」已删 —— 认领端点随批 35-B 撤除，该动作在
               online 侧不存在；且该字段渲染的是**裸 user id**（如 181），新用户读不懂。
               若需追溯「谁动过」，流转记录里那条「认领 · 人工 · user#181」仍在，信息不丢。
               ⚠️ **下一条保留**：`mode === 'claim'` 是后端 `recurrence.py:122` 的**通称**
               （`"fixed" if status == "fixed" else "claim"` = 所有非 fixed 态），不是认领的产物。 -->
          <span v-if="detail.reentry_observe && detail.reentry_observe.mode === 'claim' && detail.reentry_observe.count > 0">
            自 {{ fmtTs(detail.reentry_observe.since_ts) }} 起复发观察
          </span>
        </div>
        <!-- 批 41：原「复核窗剩余 …」倒计时与「复核窗口已超时…等待后台自动回退 open」两行已删。
             倒计时数的是**用户无法干预**的窗口（复核端点已撤除），却读起来像「你有 N 天去复核」。
             后端 `claim_ttl_job` 到期自动回退 open 这件事，改由 45s 轮询让页面自己反映状态变化
             （见 syncClaimTimers），并由流转记录里的 `claim_ttl_expire` 行留下事后解释。 -->
        <p v-if="(st === 'fixed' || st === 'claim') && showObserveCaption()" class="note-line">
          {{ reentryText() }}
        </p>
        <p v-if="(st === 'fixed' || st === 'claim') && detail.input_truncated" class="warn-line">
          {{ INPUT_TRUNCATED_WARN }}
        </p>
        <!-- 结果推送缺失（后端派生，只标示「疑似少一笔」，不展开对账）：不限状态展示——
             卡在 claim/open 等结果时它是主因，判成 fixed 后仍需可见（可能是假修复） -->
        <p v-if="detail.result_gap_suspected" class="warn-line">{{ RESULT_GAP_WARN }}</p>

        <!-- 「回查结果未达」（F-18，§8.7 保活语义）：不限状态展示——后端判据已自带
             pending/claim 期抑制/本轮性三道闸，能命中即「真在等结果」，前端**不再叠状态
             白名单**（叠了会在将来新增非终态时静默漏报，正是本标记要修的失效模式）。
             文案逐字照契约；since_ts 只作「从何时起」展示，不据此算停摆时长（两分支含义不同） -->
        <p v-if="detail.result_overdue.hit" class="warn-line">
          {{ RESULT_OVERDUE_WARN }}<template v-if="detail.result_overdue.since_ts">（自 {{ fmtTs(detail.result_overdue.since_ts) }} 起）</template>
        </p>
        <p v-if="needsReview && reasonText()" class="note-line">待人工复核原因：{{ reasonText() }}</p>
      </section>
      <!-- links 表 -->
      <section class="panel">
        <h3 class="sec">
          评测用例 link（{{ detail.links.length }}）
          <span class="sec-sub">{{ TERM.link }}：错误现场被组装成可复现的用例推给 offline 侧</span>
        </h3>
        <p v-if="detail.links.length === 0" class="muted">暂无 link</p>
        <table v-else>
          <thead>
            <tr>
              <th title="该回流簇在 offline 侧对应的评测用例编号">case_id</th>
              <th title="回流载荷的幂等键：组装 case 时生成，重填时复用同一个值">payload_id</th>
              <th>类型</th>
              <th>offline 状态</th>
              <th>回查状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lk in detail.links" :key="lk.link_id">
              <td class="mono">{{ lk.case_id || '-' }}</td>
              <td class="mono short">{{ lk.payload_id }}</td>
              <td>{{ lk.case_type || '-' }}</td>
              <td>
                <span class="status" :class="statusCls(lk.offline_status)">{{ offlineLabel(lk.offline_status) }}</span>
                <div v-if="lk.offline_status === 'invalidated' && lk.invalidate_reason" class="muted small">
                  {{ INVALIDATE_REASON_NOTE[lk.invalidate_reason] ?? lk.invalidate_reason }}
                </div>
              </td>
              <td>
                {{ verifyLabel(lk) }}
                <span v-if="lk.verify_status === 'failed'" class="red-dot">fail</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- verify_runs 版本×结果时间线 -->
      <section class="panel">
        <h3 class="sec">
          回归验证 run（{{ detail.verify_runs.length }}）
          <span class="sec-sub">offline 侧用该用例回跑的结果：连续通过 K 次才判「已修复」</span>
        </h3>
        <p v-if="detail.verify_runs.length === 0" class="muted">
          暂无回归 run——现行 link 待 offline 拉取/回查后由 offline 侧出 run
        </p>
        <div v-else class="tl">
          <div v-for="r in detail.verify_runs" :key="r.record_id" class="tl-row">
            <span class="run-status" :class="r.case_pass ? 'ok' : 'fail'">
              {{ r.case_pass ? 'pass' : 'fail' }}
            </span>
            <span class="mono">run {{ r.run_id }}</span>
            <span class="muted">v{{ r.bound_version }}</span>
            <span class="muted">状态 {{ r.run_status }}</span>
            <span v-if="r.excluded_hit" class="warn-tag">excluded</span>
            <span class="muted tl-ts">{{ fmtTs(r.verified_ts) }}</span>
          </div>
        </div>
      </section>

      <!-- conversions 审计时间线 -->
      <section class="panel">
        <h3 class="sec">
          流转记录（{{ detail.conversions.length }}）
          <span class="sec-sub">这簇错误被谁在什么时候动过：认领 / 复核 / 重开 / 失效…</span>
        </h3>
        <p v-if="detail.conversions.length === 0" class="muted">暂无流转记录</p>
        <div v-else class="tl">
          <div v-for="c in convRows" :key="c.record_id" class="tl-row">
            <span class="act-tag">{{ conversionActionLabel(c.action) }}</span>
            <!-- 批 31：原来一律「操作人 xxx」，系统自动动作与人工动作**同形** ——
                 这正是「系统背着我干了什么」看不出来的原因之一。
                 判据用 `actor_user_id`，不硬编码 action 名：实测该字段与动作性质
                 100% 对齐（assemble/auto_fixed/regression_result 全为 null；
                 claim/config_change/requeue 全有值）。 -->
            <span class="muted who" :class="{ sys: c.actor_user_id === null }">
              {{ c.actor_user_id === null ? '系统自动' : `人工 · ${actorName(c)}` }}
            </span>
            <span class="muted tl-ts">{{ fmtTs(c.ts) }}</span>
            <!-- P1-13：claim 的 detail 是认领表单 JSON 原文，渲染成人话（解析失败回退原文） -->
            <span class="tl-detail">{{ conversionDetailText(c.action, c.detail) }}</span>
          </div>
        </div>
        <!-- 批 31：一条不删，只是不再让第一屏被流水淹没 -->
        <button
          v-if="detail.conversions.length > CONV_PREVIEW"
          class="btn-ghost more" type="button" @click="showAllConv = !showAllConv"
        >{{ showAllConv ? '收起' : `展开全部 ${detail.conversions.length} 条` }}</button>
      </section>
    </template>
    <p v-else-if="!loading && !detail" class="muted">该 cluster 不存在或已删除</p>
  </div>
</template>

<style scoped>
/* 页头一句话（批 29）：新手进页第一眼要知道「这页在讲什么、从哪读起」 */
.intro {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-left: 3px solid var(--brand);
  background: var(--panel);
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
}

/* 「现在轮谁」两条车道（批 30）：左标签定宽、两行文案左侧对齐，便于上下对照。
   高亮**只给「需要你」那条、且仅当 mine**：系统自动那条永远中性 —— 两条都亮等于都没亮。 */
.lanes {
  margin: 0 0 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}

.lane {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 12px;
  background: var(--panel);
  font-size: 13px;
  line-height: 1.6;
}

.lane + .lane { border-top: 1px solid var(--border); }

.lane-tag {
  flex: 0 0 64px;
  font-size: 12px;
  color: var(--muted);
}

.lane-text { color: var(--text); }

.lane.need { background: var(--hl-red); }
.lane.need .lane-tag { color: var(--error); font-weight: 600; }

/* 批 31：系统自动 / 人工用颜色分开（原来同形） */
.who.sys { color: var(--timeout); }
.more { margin-top: 8px; }

/* 区标题下的小字释义（就地、不折叠） */
.sec-sub {
  display: block;
  margin-top: 2px;
  font-weight: 400;
  font-size: 12px;
  color: var(--muted);
}

.bar {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 12px;
}

.title {
  flex: 1;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
}

.meta {
  margin-bottom: 10px;
}

.meta-row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
}

.meta-row + .meta-row {
  margin-top: 6px;
}

.tag-mono {
  font-size: 11px;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0 4px;
}

.status {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.st-open, .st-assembled { background: #e8eaf0; color: #4b5563; }
.st-claim, .st-draft { background: #fdf1dc; color: #9a6b00; }
.st-fixed, .st-active { background: #e7f3e9; color: var(--ok); }
.st-inactive { background: #e8eaf0; color: #6b7280; }
.st-needs_review, .st-invalidated { background: var(--hl-red); color: var(--error); }

.warn-line {
  color: var(--timeout);
  background: #fdf6ec;
  border-radius: 4px;
  padding: 6px 8px;
  margin: 8px 0 0;
  font-size: 13px;
}

.note-line {
  color: var(--muted);
  background: var(--bg);
  border-radius: 4px;
  padding: 6px 8px;
  margin: 8px 0 0;
  font-size: 13px;
}

/* 批 35-B：操作区样式随人工处置写面一并删除（.ops / .ops h3.sec / .op / .op-hint
   / .op-hint em.warn / .op-hint b / .claim-form / .w-240 / .w-200 / .w-80 /
   input,.sel / .ok-text）—— 本组件模板已无任何使用者，留着会读成「功能在、只是没数据」。 */

.red-dot {
  color: var(--error);
  font-size: 12px;
}

.panel + .panel {
  margin-top: 10px;
}

.sec {
  font-size: 13px;
  margin: 0 0 8px;
  color: var(--text);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  vertical-align: top;
}

th {
  color: var(--muted);
  font-weight: 500;
  white-space: nowrap;
}

.short {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-like {
  border: none;
  background: none;
  padding: 0 4px 0 0;
  color: var(--brand);
  font-size: 13px;
  cursor: pointer;
}

.tl {
  display: flex;
  flex-direction: column;
}

.tl-row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 4px 0;
  border-bottom: 1px solid #f0f1f3;
  font-size: 13px;
}

.run-status {
  font-size: 11px;
  padding: 0 5px;
  border-radius: 3px;
  font-weight: 600;
}

.run-status.ok { background: #e7f3e9; color: var(--ok); }
.run-status.fail { background: var(--hl-red); color: var(--error); }

.act-tag {
  background: #f0f1f3;
  border-radius: 3px;
  padding: 0 6px;
  font-size: 12px;
  white-space: nowrap;
}

.warn-tag {
  color: var(--timeout);
  font-size: 12px;
}

.tl-ts {
  white-space: nowrap;
}

.tl-detail {
  flex: 1;
  color: var(--muted);
  word-break: break-all;
}
</style>
