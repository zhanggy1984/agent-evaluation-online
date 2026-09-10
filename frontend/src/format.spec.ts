// format.ts 纯函数单测（P2-6 前端测试基建首批）。
// 重点打**边界**：0 / null / undefined / 负数 / 非法 ISO。这些值在生产里都真实出现
// （后端 naive-UTC 无后缀串、空表计数、已超时 claim、跨天倒计时）。
// 时间格式化按**本地时区**渲染，故断言用同一 Date 反算期望——验的是补零与拼接口径，
// 不做时区换算假设（换算不是本模块职责）。
import { describe, expect, it } from 'vitest'
import {
  fmtAxis, fmtCountdownMs, fmtDT, fmtInt, fmtISO, fmtMs, fmtPct, fmtQps, parseISODate,
} from './format'

const pad = (n: number) => String(n).padStart(2, '0')
const localOf = (iso: string) => {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

describe('fmtDT', () => {
  it('0 视为「无值」而非 1970 纪元', () => {
    // 后端缺值可能给 0；若按时间戳渲染会显示 1970-01-01，误导排查
    expect(fmtDT(0)).toBe('-')
    expect(fmtDT(null)).toBe('-')
  })

  it('正常时间戳按本地时区补零渲染', () => {
    expect(fmtDT(Date.parse('2026-09-10T04:31:35Z'))).toBe(localOf('2026-09-10T04:31:35Z'))
  })

  it('个位数月/日/时/分/秒补零', () => {
    const s = fmtDT(Date.parse('2026-01-02T03:04:05Z'))
    expect(s).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  })
})

describe('fmtAxis', () => {
  const ts = Date.parse('2026-09-10T04:31:35Z')

  it('7d 窗到日粒度', () => {
    expect(fmtAxis(ts, '7d')).toMatch(/^\d{2}-\d{2}$/)
  })

  it('24h 窗到「日 时:00」并强制零分', () => {
    // 分钟被抹成 00：24h 视图每小时一根刻度柱，分钟会让人误读精度
    expect(fmtAxis(ts, '24h')).toMatch(/^\d{2}-\d{2} \d{2}:00$/)
  })

  it('其余窗（1h 等）到「时:分」', () => {
    expect(fmtAxis(ts, '1h')).toMatch(/^\d{2}:\d{2}$/)
    expect(fmtAxis(ts, 'unknown')).toMatch(/^\d{2}:\d{2}$/)  // 未知窗走默认分支
  })
})

describe('fmtMs', () => {
  it('null → 「-」，但 0 是合法值照渲染', () => {
    // 签名是 `number | null`（format.ts:23），undefined 不在契约内故不测；
    // 函数体内的 `v === undefined` 分支相对该签名是防御性死代码，此处不为其背书。
    expect(fmtMs(null)).toBe('-')
    expect(fmtMs(0)).toBe('0.0')   // 与 fmtDT 不同：延迟 0ms 是真实测量
  })

  it('≥10 取整、<10 保留 1 位小数', () => {
    expect(fmtMs(10)).toBe('10')
    expect(fmtMs(9.94)).toBe('9.9')
    expect(fmtMs(1234.56)).toBe('1235')
  })
})

describe('fmtPct / fmtQps / fmtInt', () => {
  it('0 是合法值，不等于「-」', () => {
    expect(fmtPct(0)).toBe('0.00%')
    expect(fmtQps(0)).toBe('0.00')
    expect(fmtInt(0)).toBe('0')
  })

  it('null/undefined → 「-」', () => {
    expect(fmtPct(null)).toBe('-')
    expect(fmtPct(undefined)).toBe('-')
    expect(fmtQps(null)).toBe('-')
    expect(fmtInt(null)).toBe('-')
  })

  it('比率按百分比保留 2 位', () => {
    expect(fmtPct(0.1234)).toBe('12.34%')
    expect(fmtPct(1)).toBe('100.00%')
  })

  it('整数按 en-US 千分位', () => {
    expect(fmtInt(1234567)).toBe('1,234,567')
  })
})

describe('parseISODate', () => {
  it('naive（无时区后缀）按 UTC 补 Z 解析', () => {
    // 后端 _iso 产出的是 naive-UTC 无后缀串；不补 Z 会被 Date 当本地时区，整体偏移数小时
    expect(parseISODate('2026-09-10T04:31:35')!.getTime())
      .toBe(Date.parse('2026-09-10T04:31:35Z'))
  })

  it('带 Z / 带偏移量的串原样解析，不重复补 Z', () => {
    expect(parseISODate('2026-09-10T04:31:35Z')!.getTime())
      .toBe(Date.parse('2026-09-10T04:31:35Z'))
    expect(parseISODate('2026-09-10T12:31:35+08:00')!.getTime())
      .toBe(Date.parse('2026-09-10T04:31:35Z'))
  })

  it('空值 / 非法串 → null（不抛异常）', () => {
    expect(parseISODate(null)).toBeNull()
    expect(parseISODate(undefined)).toBeNull()
    expect(parseISODate('')).toBeNull()
    expect(parseISODate('not-a-date')).toBeNull()
  })
})

describe('fmtISO', () => {
  it('后端 naive-UTC 串按本地时区渲染（与 parseISODate 同口径）', () => {
    expect(fmtISO('2026-09-10T04:31:35')).toBe(localOf('2026-09-10T04:31:35Z'))
  })

  it('空值 / 非法串 → 「-」', () => {
    expect(fmtISO(null)).toBe('-')
    expect(fmtISO('')).toBe('-')
    expect(fmtISO('garbage')).toBe('-')
  })
})

describe('fmtCountdownMs', () => {
  const now = Date.parse('2026-09-10T00:00:00Z')

  it('null → 「-」；已到期/已过 → 「已超时」', () => {
    expect(fmtCountdownMs(null, now)).toBe('-')
    expect(fmtCountdownMs(now, now)).toBe('已超时')      // 边界：恰好到点算超时
    expect(fmtCountdownMs(now - 1, now)).toBe('已超时')
  })

  it('不足一天的省略「天」段', () => {
    expect(fmtCountdownMs(now + 3661_000, now)).toBe('01:01:01')
  })

  it('超过一天带「天」段', () => {
    expect(fmtCountdownMs(now + (86400 + 3661) * 1000, now)).toBe('1 天 01:01:01')
  })

  it('恰好一天：天段为 1 且时分秒归零（不出现 24:00:00）', () => {
    expect(fmtCountdownMs(now + 86400_000, now)).toBe('1 天 00:00:00')
  })

  it('跨多天（claim 复核窗 14 天量级）', () => {
    expect(fmtCountdownMs(now + 14 * 86400_000, now)).toBe('14 天 00:00:00')
  })
})
