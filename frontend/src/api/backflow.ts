// 回流看板 API（P2-6 T-3.7 / detail §9.2，/backflow/*）：列表/详情读面 + 人工处置状态机写面。
// viewer 可触达 claim/ignore/reopen/needs-review 处置；admin 才调 fixed-review / link invalidate / requeue
// （后端 require_admin 二次鉴权双保险，按钮侧按 role 隐藏）。
import { api } from './client'
import type {
  BackflowClusterDetail,
  BackflowClustersResult,
  BackflowOverview,
  BackflowQuery,
} from './types'

function qs(params: BackflowQuery): string {
  const p = new URLSearchParams()
  if (params.agent) p.set('agent', params.agent)
  if (params.interface) p.set('interface', params.interface)
  if (params.layer) p.set('layer', params.layer)
  if (params.status) p.set('status', params.status)
  if (params.watch) p.set('watch', params.watch)
  if (params.page) p.set('page', String(params.page))
  if (params.page_size) p.set('page_size', String(params.page_size))
  const s = p.toString()
  return s ? `?${s}` : ''
}

export function backflowOverview(): Promise<BackflowOverview> {
  return api<BackflowOverview>('/backflow/overview')
}

export function backflowClusters(q: BackflowQuery): Promise<BackflowClustersResult> {
  return api<BackflowClustersResult>(`/backflow/clusters${qs(q)}`)
}

export function backflowClusterDetail(clusterId: number): Promise<BackflowClusterDetail> {
  return api<BackflowClusterDetail>(`/backflow/clusters/${clusterId}`)
}

// ---------- 写面（各端点失败语义同 client.ts：409 ERR_CLUSTER_0002 = 并发处置） ----------

export interface ClaimBody {
  fix_version: string
  k?: number | null
  note?: string | null
}

export interface ClaimResult {
  cluster_id: number
  fix_version: string
  claim_k: number
  claim_due_ts: string
  warning: string | null
}

export function claimCluster(clusterId: number, body: ClaimBody): Promise<ClaimResult> {
  return api<ClaimResult>(`/backflow/clusters/${clusterId}/claim`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export interface StatusResult {
  cluster_id: number
  status: string
}

export function ignoreCluster(clusterId: number): Promise<StatusResult> {
  return api<StatusResult>(`/backflow/clusters/${clusterId}/ignore`, { method: 'POST' })
}

export function reopenCluster(clusterId: number, note?: string | null): Promise<StatusResult> {
  return api<StatusResult>(`/backflow/clusters/${clusterId}/reopen`, {
    method: 'POST',
    body: JSON.stringify({ note: note ?? null }),
  })
}

export function fixedReview(clusterId: number, approve: boolean): Promise<StatusResult> {
  return api<StatusResult>(`/backflow/clusters/${clusterId}/fixed-review`, {
    method: 'POST',
    body: JSON.stringify({ approve }),
  })
}

export interface NeedsReviewResolveResult {
  cluster_id: number
  status: string
  action: string
}

// needs_review 单条处置：action ∈ {reopen_cluster, escalated}（escalated = 记录保留）
export function needsReviewResolve(
  clusterId: number, action: 'reopen_cluster' | 'escalated', note?: string | null,
): Promise<NeedsReviewResolveResult> {
  return api<NeedsReviewResolveResult>(
    `/backflow/clusters/${clusterId}/needs-review-resolve`, {
      method: 'POST',
      body: JSON.stringify({ action, note: note ?? null }),
    },
  )
}

export interface BatchResolveResult {
  batch_id: number
  action: string
  results: { cluster_id: number; status: string; detail?: string | null }[]
}

// unclean_run 批处置（整批）：action ∈ {reopen_cluster, escalated}，缺省 reopen_cluster
export function batchResolve(
  batchId: number, action: 'reopen_cluster' | 'escalated' = 'reopen_cluster',
): Promise<BatchResolveResult> {
  return api<BatchResolveResult>(`/backflow/needs-review-batches/${batchId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
}

export interface LinkInvalidateResult {
  link_id: number
  payload_id: string
  offline_status: string
}

// admin：offline_status∈{assembled,draft} 的现行 link 失效（结构自检失败/现场修正）
export function linkInvalidate(linkId: number, reason?: string | null): Promise<LinkInvalidateResult> {
  return api<LinkInvalidateResult>(`/backflow/links/${linkId}/invalidate`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason ?? null }),
  })
}

export interface LinkRequeueResult {
  link_id: number
  payload_id: string
  offline_status: string
  assembled_ts: string
  // R-7 可愈性标注：本次之前的重推次数（不含本次），与后端 requeue_link 返回同口径
  requeue_count?: number
}

// admin：invalidated∧verify pending∧cluster∈{open,claim,needs_review} 的重推（复用 payload 增量锚）
export function linkRequeue(linkId: number): Promise<LinkRequeueResult> {
  return api<LinkRequeueResult>(`/backflow/links/${linkId}/requeue`, { method: 'POST' })
}
