// 动态 agent 列表（Q4/Q5 决策）：数据源 = GET /metrics/agents（近 7d 实测去重，非写死白名单）。
// 模块级单例 + single-flight：下拉与链路页共享同一份；首载失败留空不阻断（下拉仅"全站"），可手动重试。
import { ref } from 'vue'

import { ApiError } from '../api/client'
import { metricsAgents } from '../api/metrics'

const agents = ref<string[]>([])
const total = ref(0)
const truncated = ref(false)
const loading = ref(false)
const errorMsg = ref('')
let inFlight: Promise<void> | null = null
let lastLoadAt = 0

async function doLoad(force = false): Promise<void> {
  if (inFlight) return inFlight
  if (force === false && (agents.value.length > 0 || errorMsg.value)) return // 已有结果不再重复拉
  loading.value = true
  errorMsg.value = ''
  inFlight = (async () => {
    try {
      const r = await metricsAgents()
      agents.value = r.agents
      total.value = r.total
      truncated.value = r.truncated
      lastLoadAt = Date.now() // 可见性刷新的节流基准（切回前台 >60s 才重拉）
    } catch (e) {
      // 401 由 client 终局广播接管（跳登录）；其余失败 → 下拉退化仅"全站"，页面主体不受影响
      if (!(e instanceof ApiError && e.status === 401)) {
        errorMsg.value = 'agent 列表加载失败'
      }
    } finally {
      loading.value = false
      inFlight = null
    }
  })()
  return inFlight
}

export function useAgents(): {
  agents: typeof agents
  total: typeof total
  truncated: typeof truncated
  loading: typeof loading
  errorMsg: typeof errorMsg
  load: (force?: boolean) => Promise<void>
  lastLoadMs: () => number
} {
  return { agents, total, truncated, loading, errorMsg, load: doLoad, lastLoadMs: () => lastLoadAt }
}
