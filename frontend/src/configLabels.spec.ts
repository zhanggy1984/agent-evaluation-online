// configLabels.ts 单测（P0-3）。断言重心不是「文案好看」，而是两条不变量：
// ① **live 标记与后端读取点取证一致** —— 这页最容易犯的错就是把「登记了但无人读」的键
//    写成正常配置项，故 dead 键集合在此**逐字钉死**（改后端读取点必须同步改这里）；
// ② **未知键不崩、不硬造说明**（键集非闭合）。
import { describe, expect, it } from 'vitest'
import { CONFIG_KEY_INFO, configKeyDesc, configKeyInfo, configKeyIsDead } from './configLabels'

// 2026-09-18 grep `backend/` 整仓（get_global_int / get_global_config 调用方）所得的两组键。
const LIVE_KEYS = [
  'claim_ttl_days',
  'auto_fixed_k_default',
  'auto_requeue_max_default',
  'rollup_late_k_h',
  'keyword_search_days',
  'trace_query_timeout_ms',
  'metric_agg_cache_ttl_s',
  'metric_agg_timeout_ms',
  'trace_judge_purge_days',
]
const DEAD_KEYS = [
  'cluster_window_days',
  'llm_call_observe_window_min',
  'llm_call_observe_threshold',
  'trace_judge_window_s',
  'trace_judge_grace_s',
]

describe('CONFIG_KEY_INFO', () => {
  // ⚠️ 本断言比的是**本文件写死的两张表**，不是真去读 seed.py ⇒ 后端加键而此处没加**不会红**。
  // 它是「我写完两张表后自洽」的证据，不是「两边同步」的证据（数已随批 37 由 13 → 14）。
  it('键集全等：覆盖 seed 的 14 个全局键，不多不少', () => {
    expect(Object.keys(CONFIG_KEY_INFO).sort()).toEqual([...LIVE_KEYS, ...DEAD_KEYS].sort())
  })

  it('live 标记与后端读取点取证逐键一致', () => {
    for (const k of LIVE_KEYS) {
      expect(CONFIG_KEY_INFO[k].live, `${k} 应标 live`).toBe(true)
    }
    for (const k of DEAD_KEYS) {
      expect(CONFIG_KEY_INFO[k].live, `${k} 应标 dead`).toBe(false)
    }
  })

  it('每个键都有非空说明（不留裸键名给新手）', () => {
    for (const [k, v] of Object.entries(CONFIG_KEY_INFO)) {
      expect(v.desc.trim(), `${k} 缺说明`).not.toBe('')
    }
  })
})

describe('configKeyDesc', () => {
  it('live 键只给说明：不含「未读取」字样，免得把能用的键说成死的', () => {
    const s = configKeyDesc('claim_ttl_days')
    expect(s).toContain('天')
    expect(s).not.toContain('未读取')
  })

  it('dead 键必须显式标「改动不生效」，且保留说明不吞掉', () => {
    const s = configKeyDesc('cluster_window_days')
    expect(s).toContain('未读取')
    expect(s).toContain('不生效')
    expect(s).toContain('聚类去重窗口')
  })

  it('未知键返回空串（键集非闭合，不硬造说明、不崩）', () => {
    expect(configKeyDesc('brand_new_key')).toBe('')
    expect(configKeyInfo('brand_new_key')).toBeNull()
  })

  it('未知键不误判为 dead（没有说明 ≠ 已证实无读取点）', () => {
    expect(configKeyIsDead('brand_new_key')).toBe(false)
    expect(configKeyIsDead('cluster_window_days')).toBe(true)
  })
})
