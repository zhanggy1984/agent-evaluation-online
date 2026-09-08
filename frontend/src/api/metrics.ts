// 指标 API（detail §8.4，T-2.2）：四端点，window ∈ {1h,24h,7d}，agent 缺省 = 全站。
import { api } from './client'
import type {
  MetricsAnomalies,
  MetricsInterfaces,
  MetricsLlmFailures,
  MetricsOverview,
} from './types'

function qs(params: { agent?: string | null; window: string }): string {
  const p = new URLSearchParams()
  if (params.agent) p.set('agent', params.agent)
  p.set('window', params.window)
  const s = p.toString()
  return s ? `?${s}` : ''
}

export function metricsOverview(agent: string | null, window: string): Promise<MetricsOverview> {
  return api<MetricsOverview>(`/metrics/overview${qs({ agent, window })}`)
}

export function metricsInterfaces(agent: string | null, window: string): Promise<MetricsInterfaces> {
  return api<MetricsInterfaces>(`/metrics/interfaces${qs({ agent, window })}`)
}

export function metricsAnomalies(agent: string | null, window: string): Promise<MetricsAnomalies> {
  return api<MetricsAnomalies>(`/metrics/anomalies${qs({ agent, window })}`)
}

export function metricsLlmFailures(
  agent: string | null, window: string,
): Promise<MetricsLlmFailures> {
  return api<MetricsLlmFailures>(`/metrics/llm-failures${qs({ agent, window })}`)
}
