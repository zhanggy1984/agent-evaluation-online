// loginLock.ts 单测（P0-5）。断言重心 = **拿不到值时不显示倒计时**：
// 显示一个走完却仍然进不去的计时器，比没有倒计时更糟（它会让用户反复重试并怀疑系统坏了）。
import { describe, expect, it } from 'vitest'
import { ApiError } from './api/client'
import { formatCountdown, retryAfterSeconds } from './loginLock'

const locked = (extra: Record<string, unknown>) =>
    new ApiError(423, 'ERR_AUTH_0003', '登录失败次数过多，已锁定 15 分钟', extra)

describe('retryAfterSeconds', () => {
  it('423 带 retry_after_s → 取到整数秒', () => {
    expect(retryAfterSeconds(locked({ retry_after_s: 900 }))).toBe(900)
    expect(retryAfterSeconds(locked({ retry_after_s: 99.7 }))).toBe(99)
  })

  it('非 423 一律不显示倒计时（401 只是密码错，没有锁定）', () => {
    expect(retryAfterSeconds(new ApiError(401, 'ERR_AUTH_0001', '用户名或密码错误'))).toBeNull()
  })

  it('423 但字段缺失/非法 → null（老后端或形状变了也不显示错的数）', () => {
    expect(retryAfterSeconds(locked({}))).toBeNull()
    expect(retryAfterSeconds(locked({ retry_after_s: '900' }))).toBeNull()
    expect(retryAfterSeconds(locked({ retry_after_s: 0 }))).toBeNull()
    expect(retryAfterSeconds(locked({ retry_after_s: -5 }))).toBeNull()
    expect(retryAfterSeconds(locked({ retry_after_s: Number.NaN }))).toBeNull()
  })

  it('非 ApiError（网络层抛的 TypeError 等）→ null，不崩', () => {
    expect(retryAfterSeconds(new TypeError('Failed to fetch'))).toBeNull()
    expect(retryAfterSeconds(undefined)).toBeNull()
  })
})

describe('formatCountdown', () => {
  it('mm:ss 补零', () => {
    expect(formatCountdown(900)).toBe('15:00')
    expect(formatCountdown(100)).toBe('01:40')
    expect(formatCountdown(9)).toBe('00:09')
    expect(formatCountdown(0)).toBe('00:00')
  })

  it('负数/非法值按 0（倒计时走到头不显示 -1:-1）', () => {
    expect(formatCountdown(-3)).toBe('00:00')
    expect(formatCountdown(Number.NaN)).toBe('00:00')
  })
})
