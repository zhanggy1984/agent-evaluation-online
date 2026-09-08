// 指标四页共享筛选（Q3 决策：24h/全站 默认，切页保持、刷新保留）。
// 不引 pinia：模块级单例 reactive + localStorage 持久化（键 obs.metricFilter），
// 模块级即跨视图共享 → 各页 watch 同一 state 即可联动重拉。
import { reactive, watch } from 'vue'

export type WindowKey = '1h' | '24h' | '7d'

export const WINDOWS: { v: WindowKey; label: string }[] = [
  { v: '1h', label: '近 1 小时' },
  { v: '24h', label: '近 24 小时' },
  { v: '7d', label: '近 7 天' },
]

export interface MetricFilter {
  window: WindowKey
  agent: string // '' = 全站
}

const KEY = 'obs.metricFilter'
const VALID_WINDOWS: WindowKey[] = ['1h', '24h', '7d']

function readStored(): MetricFilter {
  const dft: MetricFilter = { window: '24h', agent: '' }
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return dft
    const p = JSON.parse(raw) as Partial<MetricFilter>
    const window_ = VALID_WINDOWS.includes(p.window as WindowKey) ? p.window as WindowKey : dft.window
    return { window: window_, agent: typeof p.agent === 'string' ? p.agent : dft.agent }
  } catch {
    return dft
  }
}

// 模块级单例：切页状态保持（组件卸载不丢），多页 watch 同一对象
const state = reactive<MetricFilter>(readStored())

watch(state, (v) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(v))
  } catch {
    /* localStorage 不可用（隐私模式等）：仅内存态，不阻断 */
  }
})

export function useMetricFilter(): { filter: MetricFilter } {
  return { filter: state }
}
