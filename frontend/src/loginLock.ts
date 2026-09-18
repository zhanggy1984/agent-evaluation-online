// 登录锁定倒计时（P0-5）。**剩余秒数只有服务端算得出来**：锁定是 900s 滑动窗口上的失败计数，
// 解锁时刻 = **最早**那次失败滑出窗口（`backend/app/api/auth.py` 的 `_check_locked`）——
// 客户端不知道「第一次失败发生在什么时候」（可能在本会话之前，也可能是别的标签页造的），
// 所以这里**只做展示，不本地推算**：拿不到服务端给的值就**不显示倒计时**，
// 宁可不说，也不给一个走完却仍然进不去的计时器。
import { ApiError } from './api/client'

/** 从 423 响应里取服务端给的剩余秒数；非 423 / 字段缺失 / 非正数 → null。 */
export function retryAfterSeconds(err: unknown): number | null {
  if (!(err instanceof ApiError) || err.status !== 423) return null
  const raw = err.extra.retry_after_s
  if (typeof raw !== 'number' || !Number.isFinite(raw) || raw <= 0) return null
  return Math.floor(raw)
}

/** 秒 → `mm:ss`（负数按 0 处理；超过 99 分钟不进位到时，避免倒计时比锁定时长还吓人）。 */
export function formatCountdown(sec: number): string {
  const s = Number.isFinite(sec) ? Math.max(0, Math.floor(sec)) : 0
  const mm = Math.floor(s / 60)
  const ss = s % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
