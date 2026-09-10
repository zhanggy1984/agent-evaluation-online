// 看板共用格式化（T-2.4）：时间 / 分位数延迟 / 比率 / 计数。
// 单独成模块：四区块 + 图表 xFmt/yFmt 都要用，避免各组件重复 fmtTs。

const pad = (n: number): string => String(n).padStart(2, '0')

// 完整时间 YYYY-MM-DD HH:mm:ss（表内列）
export function fmtDT(ts: number | null): string {
  if (!ts) return '-'
  const d = new Date(ts)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 图表 x 轴短标签：按时间窗给刻度粒度（1h 分钟 / 24h 到分钟 / 7d 到日）
export function fmtAxis(ts: number, window: string): string {
  const d = new Date(ts)
  if (window === '7d') return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (window === '24h') return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:00`
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 分位数延迟（ms）：空 → '-'；去尾零保留 1 位小数（p50 常是小数 ms）
export function fmtMs(v: number | null): string {
  if (v === null || v === undefined) return '-'
  const s = v >= 10 ? v.toFixed(0) : v.toFixed(1)
  return s
}

// 比率 0..1 → 百分比
export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  return `${(v * 100).toFixed(2)}%`
}

export function fmtQps(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  return v.toFixed(2)
}

export function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '-'
  return v.toLocaleString('en-US')
}

// ---- 回流看板（P2-6）：后端 _iso 的 naive-UTC 无后缀字符串 + claim_due_ts 的 Z 后缀，统一解析 ----

// naive（无时区后缀）按 UTC 补 Z 再解析；无法解析 → null
export function parseISODate(v: string | null | undefined): Date | null {
  if (!v) return null
  const s = /(Z|[+-]\d{2}:?\d{2})$/.test(v) ? v : `${v}Z`
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? null : d
}

// 表列 ISO → 本地 YYYY-MM-DD HH:mm:ss（与 fmtDT 同展示口径）
export function fmtISO(v: string | null | undefined): string {
  const d = parseISODate(v)
  if (!d) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 截止时刻倒计时：`X 天 HH:MM:SS`；已过 → 「已超时」
export function fmtCountdownMs(untilMs: number | null, nowMs: number): string {
  if (untilMs === null || untilMs === undefined) return '-'
  const diff = untilMs - nowMs
  if (diff <= 0) return '已超时'
  const pad = (n: number) => String(n).padStart(2, '0')
  const days = Math.floor(diff / 86400000)
  const rem = diff - days * 86400000
  const h = Math.floor(rem / 3600000)
  const m = Math.floor((rem % 3600000) / 60000)
  const s = Math.floor((rem % 60000) / 1000)
  return days > 0
    ? `${days} 天 ${pad(h)}:${pad(m)}:${pad(s)}`
    : `${pad(h)}:${pad(m)}:${pad(s)}`
}
