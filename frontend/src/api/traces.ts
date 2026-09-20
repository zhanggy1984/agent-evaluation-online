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
  // P1-10 后半（2026-09-20）：时间窗。**不传 = 后端回退 keyword_search_days**（=7）。
  if (q.start_ts) params.set('start_ts', String(q.start_ts))
  if (q.page) params.set('page', String(q.page))
  if (q.page_size) params.set('page_size', String(q.page_size))
  const qs = params.toString()
  return api<ListTracesResult>(`/traces${qs ? `?${qs}` : ''}`)
}

export function traceDetail(agent: string, traceId: string): Promise<TraceDetail> {
  return api<TraceDetail>(`/traces/${encodeURIComponent(agent)}/${encodeURIComponent(traceId)}`)
}

// 日志正文放行（2026-09-20 用户拍板，**契约层面的选择、不是修 bug**）：
// log_message 受 body_search 门控（v1.1 约定，后端 detail §8.2 注 / §13.4 两层 —— ① 检索面
// 收窄到 error 字段 ② 序列化前把 input/output/log_message 置 None），默认 false。
// 前端此前不传 ⇒ 拿到的恒为 None，页面只能渲染「日志正文默认不返回」的占位。
// 现由前端**显式**带 true：这层默认保护在 UI 的日志路径上从此不再生效。默认值本身没改，
// curl / S-5 验收口径不变。
// ⚠️ **只给日志这一个请求带。** body_search 同时是**检索面总闸**（后端 docstring ①：
// store 层 multi_match fields 随开关收窄），而详情页/列表页**没有任何 input/output 渲染点**
// （详情列只有 seq/节点/接口/model/usage/时间/耗时/状态）⇒ 给它们带 true 是纯放开正文面、
// 零可见收益。下方两条 spec 就是钉这个边界的。
export function traceLogs(
  agent: string, traceId: string, page: number, pageSize: number,
): Promise<Page<TraceLogRow>> {
  return api<Page<TraceLogRow>>(
    `/traces/${encodeURIComponent(agent)}/${encodeURIComponent(traceId)}/logs` +
      `?page=${page}&page_size=${pageSize}&body_search=true`,
  )
}
