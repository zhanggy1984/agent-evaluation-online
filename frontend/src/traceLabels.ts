// 链路详情文案（P0-1）：error_type → 一句话解释 + 失败详情拼装。
//
// error_type 值域**非闭合**（backend/app/consumer/schema.py §2.5：全集 + `auth_error`/
// `validation_error` 等业务扩展，消费层只校验「status=error 必填 + 长度 ≤48」，不做枚举拒绝）
// ⇒ 映射表只覆盖 `HTTP_<码>` 与 `llm_` 两类前缀，**未知值一律原样透传**：
// 绝不因「表里没有」而吞掉原值（吞了就等于把后端的业务扩展信息在 UI 上抹掉）。

// 常见 HTTP 状态码 → 新手能读的一句话。表外码按 4xx/5xx 给类，仍表外则只留码本身。
const HTTP_HINT: Record<number, string> = {
  400: '请求格式有误',
  401: '未认证（凭证缺失或已失效）',
  403: '无权限访问',
  404: '接口地址不存在',
  409: '与现有数据冲突',
  422: '参数未通过校验',
  429: '请求过于频繁被限流',
  500: '上游服务内部错误',
  502: '网关错误（上游不可达）',
  503: '上游服务不可用',
  504: '网关超时（上游未及时响应）',
}

export function errorTypeHint(t: string): string {
  const m = /^HTTP_(\d{3})$/.exec(t)
  if (m) {
    const code = Number(m[1])
    const known = HTTP_HINT[code]
    if (known) return known
    if (code >= 400 && code < 500) return '请求被上游拒绝'
    if (code >= 500 && code < 600) return '上游服务故障'
    return ''
  }
  if (t.startsWith('llm_')) return 'LLM 调用失败'
  return ''
}

// 失败详情（P0-1）。request 级 error 现状只采到状态码、源头无 error_msg（2026-09-18 取证：
// node=request 且 status=error 共 152 条、error_msg 全空；对照组 llm_call 级有且 API 原样下发）
// ⇒ 无消息时**显式说明**，而不是照旧拼出一行裸码「HTTP_422」——那读起来像「有错但查不到」。
export interface ErrorRowLike {
  // 对齐视图侧实际用到的行类型（其 status 是 string|null，非 TraceEventRow 的字面量联合）：
  // null 落到下面的 error 分支，与「不该发生但兜底不崩」同路。
  status: string | null
  error_type?: string | null
  error_msg?: string | null
}

export function errorDetail(row: ErrorRowLike): string {
  if (row.status === 'timeout') {
    return row.error_msg ? `调用超时：${row.error_msg}` : '调用超时（未在阈值内返回）'
  }
  const t = row.error_type || ''
  const hint = t ? errorTypeHint(t) : ''
  const head = hint ? `${t}（${hint}）` : t
  if (!head) return row.error_msg || '执行失败，未上报错误消息'
  return row.error_msg ? `${head}：${row.error_msg}` : `${head} · 未上报错误消息详情`
}
