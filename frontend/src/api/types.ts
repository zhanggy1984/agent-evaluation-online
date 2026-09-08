// 与 detail §8 响应模型同构的类型（后端为准，字段缺省可空）。
export interface UserOut {
  id: number
  username: string
  display_name: string | null
  role: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  user: UserOut
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface TraceListItem {
  agent: string | null
  trace_id: string | null
  interface: string | null
  node: string | null
  status: string | null
  error_type: string | null
  error_msg: string | null
  ts: number | null
}

export interface TraceEventRow {
  seq: number | null
  node: string | null
  parent: number | null
  branch: number | null
  interface: string | null
  status: string | null
  error_type: string | null
  error_msg: string | null
  ts: number | null
  duration_ms: number | null
  model: string | null
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null
  input: string | null
  output: string | null
}

export interface TraceDetail {
  agent: string
  trace_id: string
  events: TraceEventRow[]
  total: number
  truncated: boolean
}

export interface TraceLogRow {
  seq: number | null
  ts: number | null
  log_level: string | null
  log_message: string | null
}

// 查询参数（GET /traces，detail §8.2）
export interface TraceQuery {
  trace_id?: string
  keyword?: string
  agent?: string
  interface?: string
  page?: number
  page_size?: number
}

// ---------- 指标（detail §8.4 + §14.4，T-2.2/T-2.3；字段与后端 pydantic 逐一对齐） ----------

// source: rollup | realtime | mixed；fallback_hours = 回退实时的小时起点（epoch ms，7d）
export interface MetricsCards {
  qps: number | null
  p50: number | null
  p95: number | null
  p99: number | null
  total: number
  error: number
  timeout: number
  error_rate: number | null
  timeout_rate: number | null
}

export interface OverviewSeriesPoint {
  ts: number
  count: number
  qps: number | null
  error_rate: number | null
  timeout_rate: number | null
}

export interface MetricsOverview {
  window: string
  agent: string | null
  source: string
  fallback_hours: number[]
  // 7d 卡片分位 merge 的已 rollup 小时数（1h/24h 恒 0）；UI 分位标注依据（v1.14）
  covered_hours: number
  cards: MetricsCards
  series: OverviewSeriesPoint[]
}

export interface ReqIfaceRow {
  interface: string
  total: number
  error: number
  timeout: number
  p50: number | null
  p95: number | null
  p99: number | null
}

export interface LlmModelRow {
  model: string
  total: number
  error: number
  prompt_tokens: number
  completion_tokens: number
}

export interface LlmIfaceRow {
  interface: string
  total: number
  error: number
  llm_failure_rate: number | null
  models: LlmModelRow[]
}

export interface MetricsInterfaces {
  window: string
  agent: string | null
  source: string
  fallback_hours: number[]
  request: ReqIfaceRow[]
  llm: LlmIfaceRow[]
}

export interface AnomalyItem {
  agent: string | null
  trace_id: string | null
  interface: string | null
  status: string | null
  error_type: string | null
  error_msg: string | null
  ts: number | null
  duration_ms: number | null
}

export interface MetricsAnomalies {
  window: string
  agent: string | null
  // total = 窗口内真实条数；truncated = size≤100 截断（UI 提示"仅显示最新 N 条"，v1.14）
  total: number
  truncated: boolean
  items: AnomalyItem[]
}

export interface LlmFailureItem {
  agent: string | null
  trace_id: string | null
  interface: string | null
  request_status: string | null
  llm_node_status: string | null
  llm_error_type: string | null
  llm_error_msg: string | null
  model: string | null
  ts: number | null
}

export interface MetricsLlmFailures {
  window: string
  agent: string | null
  // total = 窗口内**失败 trace 去重数**；truncated = 折叠列表 size≤100 截断（v1.14）
  total: number
  truncated: boolean
  items: LlmFailureItem[]
}

// GET /metrics/agents：近 7d 有流量的 agent 名（纯实测、按频次降序）——筛选下拉数据源。
// total = 真实去重 agent 总数（distinct agg），可 > len(agents)（top100 截断）；truncated 据此。
export interface MetricsAgents {
  total: number
  truncated: boolean
  agents: string[]
}
