// 动态 agent 列表（Q4/Q5 决策）：数据源 = GET /metrics/agents（近 7d 实测去重，非写死白名单）。
// 模块级单例 + single-flight：下拉与链路页共享同一份；首载失败留空不阻断（下拉仅"全站"），可手动重试。
import { ref } from 'vue'

import { ApiError } from '../api/client'
import { metricsAgents } from '../api/metrics'

const agents = ref<string[]>([])
const loading = ref(false)
const errorMsg = ref('')
let inFlight: Promise<void> | null = null

async function doLoad(force = false): Promise<void> {
  if (inFlight) return inFlight
  if (force === false && (agents.value.length > 0 || errorMsg.value)) return // 已有结果不再重复拉
  loading.value = true
  errorMsg.value = ''
  inFlight = (async () => {
    try {
      agents.value = (await metricsAgents()).agents
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
  loading: typeof loading
  errorMsg: typeof errorMsg
  load: (force?: boolean) => Promise<void>
} {
  return { agents, loading, errorMsg, load: doLoad }
}
