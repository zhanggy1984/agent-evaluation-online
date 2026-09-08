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
