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
