// trace 查询 API（detail §8.2）：检索列表 / 详情 / 日志懒加载。
import { api } from './client'
import type { Page, TraceDetail, TraceListItem, TraceLogRow, TraceQuery } from './types'

export interface ListTracesResult extends Page<TraceListItem> {
  // 向后兼容扩展位（如需 keyword 命中统计等，后端补字段后再加）
}

export function listTraces(q: TraceQuery): Promise<ListTracesResult> {
  const params = new URLSearchParams()
  if (q.trace_id) params.set('trace_id', q.trace_id)
  if (q.keyword) params.set('keyword', q.keyword)
  if (q.agent) params.set('agent', q.agent)
  if (q.interface) params.set('interface', q.interface)
  // P1-11：此前**漏了这一行** —— 组件把 status 传进来、类型上是多余的属性却因
  // 「先赋值给变量再传参」而不报错，于是 URL 里根本没有 status，过滤静默失效。
  // 真机取证时落点页读到的是「不限 status」的条数，被我误当成窗口差异解释掉了。
  if (q.status) params.set('status', q.status)
  if (q.page) params.set('page', String(q.page))
  if (q.page_size) params.set('page_size', String(q.page_size))
  const qs = params.toString()
  return api<ListTracesResult>(`/traces${qs ? `?${qs}` : ''}`)
}

export function traceDetail(agent: string, traceId: string): Promise<TraceDetail> {
  return api<TraceDetail>(`/traces/${encodeURIComponent(agent)}/${encodeURIComponent(traceId)}`)
}

export function traceLogs(
  agent: string, traceId: string, page: number, pageSize: number,
): Promise<Page<TraceLogRow>> {
  return api<Page<TraceLogRow>>(
    `/traces/${encodeURIComponent(agent)}/${encodeURIComponent(traceId)}/logs` +
      `?page=${page}&page_size=${pageSize}`,
  )
}
