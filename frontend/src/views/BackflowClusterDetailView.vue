<script setup lang="ts">
// cluster 详情页（P2-6 T-3.7 / detail §9.2 独立路由 backflow-cluster）：元数据 + links 表 +
// verify_runs 版本×pass/fail 时间线 + conversions 审计时间线 + 人工处置动作区（按状态门控）。
// 角色：viewer 恒见 claim/ignore/reopen/needs-review 处置；admin 才渲染 fixed-review / invalidate / requeue。
// claim 复核窗：本地 1s tick 倒计时 + 45s 后台轮询（visibility=visible 时）侦测 TTL 自动回退 open。
// 时间戳 = 后端 _iso naive-UTC 字符串 → fmtISO / parseISODate。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  backflowClusterDetail,
  batchResolve,
  claimCluster,
  fixedReview,
  ignoreCluster,
  linkInvalidate,
  linkRequeue,
  needsReviewResolve,
  reopenCluster,
} from '../api/backflow'
import { ApiError, readStoredUser } from '../api/client'
import type { BackflowClusterDetail, BackflowLink } from '../api/types'
import {
  CLUSTER_STATUS_LABEL,
  conversionActionLabel,
  INVALIDATE_REASON_NOTE,
  INPUT_TRUNCATED_WARN,
  OFFLINE_STATUS_TEXT,
  reentryCaption,
  RESULT_GAP_WARN,
  REVIEW_REASON_TEXT,
  VERIFY_STATUS_TEXT,
} from '../backflowLabels'
import { fmtCountdownMs, fmtISO, parseISODate } from '../format'

const route = useRoute()
const router = useRouter()
const clusterId = Number(route.params.clusterId)

const isAdmin = readStoredUser()?.role === 'admin'

const detail = ref<BackflowClusterDetail | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const actionMsg = ref('')
const actionErr = ref('')
const busy = ref(false)

// claim 复核窗本地倒计时（1s tick）与 45s 轮询
const now = ref(Date.now())
let tickId: number | undefined
let pollId: number | undefined

const isClaim = computed(() => detail.value?.status === 'claim')
const claimDueMs = computed(() => {
  const d = parseISODate(detail.value?.claim_due_ts)
  return d ? d.getTime() : null
})
// 复核窗已过但状态未回退（后端 TTL 轮询尚未执行）→ 提示等待自动回退
const claimExpired = computed(() => isClaim.value && claimDueMs.value !== null && claimDueMs.value <= now.value)

const st = computed(() => detail.value?.status ?? '')
const stLabel = computed(() => CLUSTER_STATUS_LABEL[st.value] ?? st.value)

function statusCls(s: string): string {
  return `st-${s}`
}

function fmtTs(v: string | null | undefined): string {
  return fmtISO(v)
}

// 状态门控（detail §9.4）：claim 仅 open；ignore 仅 open/claim；reopen 仅 fixed/inactive；
// needs-review 单条处置仅 needs_review；batch 仅 unclean_run 且 open_batches 命中。
const canClaim = computed(() => st.value === 'open')
const canIgnore = computed(() => st.value === 'open' || st.value === 'claim')
const canReopen = computed(() => st.value === 'fixed' || st.value === 'inactive')
const needsReview = computed(() => st.value === 'needs_review')
const hasBatch = computed(() => (detail.value?.open_batches.length ?? 0) > 0)
const openBatch = computed(() => detail.value?.open_batches[0] ?? null)

const claimForm = ref({ open: false, fix_version: '', k: '2', note: '' })

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

// 写动作统一入口：busy 防抖 + ERR_CLUSTER_0002 并发提示 + 成功后重拉 detail
async function runAction(fn: () => Promise<unknown>, okText: string): Promise<void> {
  if (busy.value) return
  busy.value = true
  actionMsg.value = ''
  actionErr.value = ''
  try {
    await fn()
    actionMsg.value = okText
    await loadDetail(false)
  } catch (e) {
    if (e instanceof ApiError) {
      actionErr.value = `（${e.code}）：${e.message}`
      if (e.code === 'ERR_CLUSTER_0002') {
        actionErr.value += '——已被并发处置，列表已刷新'
        await loadDetail(false)
      }
    } else {
      throw e
    }
  } finally {
    busy.value = false
  }
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

function openClaimForm(): void {
  claimForm.value.open = true
  claimForm.value.fix_version = detail.value?.fix_version ?? ''
  claimForm.value.k = String(detail.value?.claim_k || 2)
}

async function submitClaim(): Promise<void> {
  const fv = claimForm.value.fix_version.trim()
  if (!fv) {
    actionErr.value = 'fix_version 必填（本次修复对应的版本号）'
    return
  }
  const k = claimForm.value.k === '1' ? 1 : 2
  claimForm.value.open = false
  // 软提示不能在 fn 里写 actionMsg：runAction 随后会用 okText 覆盖同一 ref（D-2）。
  // 改为闭包带出，成功后再追加——两段文案都不丢。
  let warn: string | null = null
  await runAction(
    async () => {
      const r = await claimCluster(clusterId, {
        fix_version: fv,
        k,
        note: claimForm.value.note.trim() || null,
      })
      warn = r.warning
    },
    `已认领（K=${k}），复核窗开启`,
  )
  if (warn) actionMsg.value += `；${warn}`
}

function doIgnore(): void {
  if (!window.confirm('确认忽略该 cluster（现行 pending link 将停回查）？')) return
  void runAction(() => ignoreCluster(clusterId), '已忽略')
}

function doReopen(): void {
  if (!window.confirm('确认重开该 cluster（回到未处置，供复发/误判反悔）？')) return
  void runAction(() => reopenCluster(clusterId, null), '已重开')
}

function doFixedReview(approve: boolean): void {
  const t = approve ? '确认通过复核（claim→fixed）？' : '确认驳回复核（claim→open）？'
  if (!window.confirm(t)) return
  void runAction(() => fixedReview(clusterId, approve), approve ? '已通过复核' : '已驳回复核')
}

function doResolveSingle(action: 'reopen_cluster' | 'escalated'): void {
  const t = action === 'reopen_cluster'
    ? '确认重开该 cluster（回到未处置）？'
    : '确认 escalated（仅记录保留，状态不变）？'
  if (!window.confirm(t)) return
  void runAction(() => needsReviewResolve(clusterId, action, null),
    action === 'reopen_cluster' ? '已重开' : '已记录 escalated')
}

function doBatch(): void {
  const b = openBatch.value
  if (!b) return
  if (!window.confirm(`确认整批处置 batch#${b.batch_id}（run ${b.run_id}，${b.ref_count} 个 link 关联）为重开？`)) return
  void runAction(() => batchResolve(b.batch_id, 'reopen_cluster'), '整批已重开')
}

function doInvalidateLink(lk: BackflowLink): void {
  if (!window.confirm(`确认失效 link#${lk.link_id}（payload ${lk.payload_id}）？`)) return
  void runAction(() => linkInvalidate(lk.link_id, null), 'link 已失效')
}

function doRequeueLink(lk: BackflowLink): void {
  if (!window.confirm(`确认重推 link#${lk.link_id}（复用 payload_id 重建）？`)) return
  void runAction(() => linkRequeue(lk.link_id), 'link 已重推')
}

// link 行内 admin 动作门控：invalidate 仅 assembled/draft；requeue 仅 invalidated∧verify pending∧cluster 可处置
function linkCanInvalidate(lk: BackflowLink): boolean {
  return isAdmin && (lk.offline_status === 'assembled' || lk.offline_status === 'draft')
}

function linkCanRequeue(lk: BackflowLink): boolean {
  return isAdmin && lk.offline_status === 'invalidated' && lk.verify_status === 'pending'
    && ['open', 'claim', 'needs_review'].includes(detail.value?.status ?? '')
}

// claim 复核窗：1s 本地倒计时 tick + 45s 后台轮询（仅前台可见时拉，防后台堆积）
function syncClaimTimers(): void {
  if (isClaim.value) {
    if (tickId === undefined) tickId = window.setInterval(() => { now.value = Date.now() }, 1000)
    if (pollId === undefined) {
      pollId = window.setInterval(() => {
        if (document.visibilityState === 'visible' && !busy.value) void loadDetail(false)
      }, 45000)
    }
  } else {
    stopClaimTimers()
  }
}

function stopClaimTimers(): void {
  if (tickId !== undefined) { window.clearInterval(tickId); tickId = undefined }
  if (pollId !== undefined) { window.clearInterval(pollId); pollId = undefined }
}

watch(isClaim, (v) => { if (v) syncClaimTimers(); else stopClaimTimers() })
onMounted(() => { void loadDetail(true) })
onUnmounted(() => stopClaimTimers())

const rows = computed(() => detail.value?.conversions ?? [])
</script>

<template>
  <div>
    <header class="bar">
      <button class="btn-ghost" type="button" @click="back">← 回流看板</button>
      <strong class="title">
        cluster <span class="mono">#{{ clusterId }}</span>
        <span class="muted" v-if="detail">· {{ detail.agent }}{{ detail.interface ? `.${detail.interface}` : '' }}</span>
      </strong>
      <button class="btn-ghost" type="button" :disabled="loading" @click="loadDetail(true)">刷新</button>
    </header>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <template v-if="!loading && detail">
      <!-- 头部元信息 -->
      <section class="panel meta">
        <div class="meta-row">
          <span class="status" :class="statusCls(detail.status)">{{ stLabel }}</span>
          <span class="tag-mono">{{ detail.layer }}</span>
          <strong>{{ detail.error_type }}</strong>
          <span class="muted">{{ detail.error_msg }}</span>
        </div>
        <div class="meta-row muted small">
          <span>gen{{ detail.generation }}</span>
          <span>计数 {{ detail.count }}</span>
          <span>fix {{ detail.fix_version || '-' }}</span>
          <span>claim_k {{ detail.claim_k }}</span>
          <span>input_hash <span class="mono">{{ detail.input_hash }}</span></span>
        </div>
        <div class="meta-row muted small">
          <span>已待 {{ detail.waiting_days }} 天</span>
          <span v-if="detail.claimed_by">认领人 {{ detail.claimed_by }}（{{ fmtTs(detail.claimed_at) }}）</span>
          <span v-if="detail.reentry_observe && detail.reentry_observe.mode === 'claim' && detail.reentry_observe.count > 0">
            自 {{ fmtTs(detail.reentry_observe.since_ts) }} 起复发观察
          </span>
        </div>
        <p v-if="claimExpired" class="warn-line">复核窗口已超时（{{ fmtCountdownMs(claimDueMs, now) }}），等待后台自动回退 open…</p>
        <p v-if="isClaim && !claimExpired" class="muted small">
          复核窗剩余 {{ fmtCountdownMs(claimDueMs, now) }}
        </p>
        <p v-if="(st === 'fixed' || st === 'claim') && showObserveCaption()" class="note-line">
          {{ reentryText() }}
        </p>
        <p v-if="(st === 'fixed' || st === 'claim') && detail.input_truncated" class="warn-line">
          {{ INPUT_TRUNCATED_WARN }}
        </p>
        <!-- 结果推送缺失（后端派生，只标示「疑似少一笔」，不展开对账）：不限状态展示——
             卡在 claim/open 等结果时它是主因，判成 fixed 后仍需可见（可能是假修复） -->
        <p v-if="detail.result_gap_suspected" class="warn-line">{{ RESULT_GAP_WARN }}</p>
        <p v-if="needsReview && reasonText()" class="note-line">待人工复核原因：{{ reasonText() }}</p>
      </section>

      <p v-if="actionErr" class="error-text">操作失败{{ actionErr }}</p>
      <p v-if="actionMsg" class="ok-text">{{ actionMsg }}</p>

      <!-- 操作区（按 §9.4 状态门控） -->
      <!-- 分支顺序敏感：claim ∧ admin 必须先于 canIgnore（canIgnore 值域 ⊇ claim，
           排在前面会把复核动作整块吃掉——D-1 即此） -->
      <section v-if="canClaim || canIgnore || canReopen || needsReview" class="panel ops">
        <template v-if="canClaim">
          <button v-if="!claimForm.open" class="btn" type="button" :disabled="busy" @click="openClaimForm">
            认领并复核
          </button>
          <form v-else class="claim-form" @submit.prevent="submitClaim">
            <input v-model="claimForm.fix_version" placeholder="fix_version（必填，本次修复版本号）" class="w-240" />
            <select v-model="claimForm.k" class="sel w-80">
              <option value="2">K=2</option>
              <option value="1">K=1</option>
            </select>
            <input v-model="claimForm.note" placeholder="备注（可选）" class="w-200" />
            <button class="btn" type="submit" :disabled="busy">{{ busy ? '提交中…' : '提交认领' }}</button>
            <button class="btn-ghost" type="button" @click="claimForm.open = false">取消</button>
          </form>
          <button class="btn-ghost" type="button" :disabled="busy" @click="doIgnore">忽略</button>
        </template>
        <template v-else-if="isClaim && isAdmin">
          <button class="btn" type="button" :disabled="busy" @click="doFixedReview(true)">通过复核（→fixed）</button>
          <button class="btn-ghost" type="button" :disabled="busy" @click="doFixedReview(false)">驳回（→open）</button>
          <button class="btn-ghost" type="button" :disabled="busy" @click="doIgnore">忽略（先回退）</button>
        </template>
        <template v-else-if="canIgnore">
          <button class="btn-ghost" type="button" :disabled="busy" @click="doIgnore">
            忽略（复核中，先回退再忽略）
          </button>
        </template>
        <template v-else-if="canReopen">
          <button class="btn-ghost" type="button" :disabled="busy" @click="doReopen">重开</button>
        </template>
        <template v-else-if="needsReview">
          <button class="btn" type="button" :disabled="busy" @click="doResolveSingle('reopen_cluster')">重开（回到未处置）</button>
          <button class="btn-ghost" type="button" :disabled="busy" @click="doResolveSingle('escalated')">escalated（仅记录）</button>
          <button
            v-if="hasBatch" class="btn" type="button" :disabled="busy"
            @click="doBatch"
          >处置整批（batch#{{ openBatch?.batch_id }}，run {{ openBatch?.run_id }}，{{ openBatch?.ref_count }} link）</button>
        </template>
      </section>

      <!-- links 表 -->
      <section class="panel">
        <h3 class="sec">links（{{ detail.links.length }}）</h3>
        <p v-if="detail.links.length === 0" class="muted">暂无 link</p>
        <table v-else>
          <thead>
            <tr>
              <th>case_id</th>
              <th>payload_id</th>
              <th>类型</th>
              <th>offline 状态</th>
              <th>回查状态</th>
              <th>admin</th>
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
              <td>
                <template v-if="linkCanInvalidate(lk)">
                  <button class="link-like" type="button" :disabled="busy" @click="doInvalidateLink(lk)">失效</button>
                </template>
                <template v-if="linkCanRequeue(lk)">
                  <button class="link-like" type="button" :disabled="busy" @click="doRequeueLink(lk)">重推</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- verify_runs 版本×结果时间线 -->
      <section class="panel">
        <h3 class="sec">回查 run（{{ detail.verify_runs.length }}）</h3>
        <p v-if="detail.verify_runs.length === 0" class="muted">
          暂无回归 run——现行 link 待 offline 拉取/回查后由 offline 侧出 run
        </p>
        <div v-else class="tl">
          <div v-for="r in detail.verify_runs" :key="r.record_id" class="tl-row">
            <span class="run-status" :class="r.case_pass ? 'ok' : 'fail'">
              {{ r.case_pass ? 'pass' : 'fail' }}
            </span>
            <span class="mono">{{ r.run_id }}</span>
            <span class="muted">v{{ r.bound_version }}</span>
            <span class="muted">{{ r.run_status }}</span>
            <span v-if="r.excluded_hit" class="warn-tag">excluded</span>
            <span class="muted tl-ts">{{ fmtTs(r.verified_ts) }}</span>
          </div>
        </div>
      </section>

      <!-- conversions 审计时间线 -->
      <section class="panel">
        <h3 class="sec">流转记录（{{ detail.conversions.length }}）</h3>
        <p v-if="detail.conversions.length === 0" class="muted">暂无流转记录</p>
        <div v-else class="tl">
          <div v-for="c in rows" :key="c.record_id" class="tl-row">
            <span class="act-tag">{{ conversionActionLabel(c.action) }}</span>
            <span class="muted">{{ actorName(c) }}</span>
            <span class="muted tl-ts">{{ fmtTs(c.ts) }}</span>
            <span class="tl-detail">{{ c.detail || '' }}</span>
          </div>
        </div>
      </section>
    </template>
    <p v-else-if="!loading && !detail" class="muted">该 cluster 不存在或已删除</p>
  </div>
</template>

<style scoped>
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
  background: #f7f8fa;
  border-radius: 4px;
  padding: 6px 8px;
  margin: 8px 0 0;
  font-size: 13px;
}

.ops {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.claim-form {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}

.w-240 { width: 240px; }
.w-200 { width: 200px; }
.w-80 { width: 80px; }

input, .sel {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
}

.ok-text {
  color: var(--ok);
}

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
