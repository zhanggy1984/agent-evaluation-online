// 回流看板 API（P2-6 T-3.7 / detail §9.2，/backflow/*）：**只读三面**（总览 / 列表 / 详情）。
// ⚠️ 批 35-B：人工处置写面已整体删除（claim / ignore / reopen / needs-review-resolve /
// batch-resolve / fixed-review / link invalidate / link requeue）—— 后端端点同期撤除，
// 在此留函数只会调用到 404。簇的处置全自动：assemble_job 每 60s 组装推送 → offline 拉取执行
// → 回推 run → K 满自动 fixed。
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

