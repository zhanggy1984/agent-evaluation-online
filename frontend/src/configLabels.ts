// 配置键说明（P0-3）：`dict_config` 的键名是英文短横线串，新手看不懂「它管什么、单位是什么、
// 改了会不会生效」——尤其最后一条：库里存在**当前版本无人读取**的键，照键名猜语义会把
// 「登记项」读成「已有能力」。
//
// 语义一律**回查后端读取点**确定，不凭键名猜（读取点全集 = `get_global_int` / `get_global_config`
// 的调用方，2026-09-18 grep `backend/` 整仓）：
//   8 个有读取点：claim_ttl_days / auto_fixed_k_default / rollup_late_k_h / keyword_search_days /
//                 trace_query_timeout_ms / metric_agg_cache_ttl_s / metric_agg_timeout_ms /
//                 trace_judge_purge_days
//   5 个零读取点：cluster_window_days / llm_call_observe_window_min / llm_call_observe_threshold /
//                 trace_judge_window_s / trace_judge_grace_s
// 后者必须显式标「未读取」——否则等于替未实现的机制背书（`docs/integration-report.md:449`
// 已就 cluster_window_days 记过同一结论）。
//
// 键集**非闭合**：`dict_config` 可被直接写入新键（见 `dict_config.py` 的「库未 seed / 被删」
// 注释），故未知键返回 `null` 由调用方兜底，不在此处断言。

export interface ConfigKeyInfo {
  /** 一句话说明：管什么 + 单位。 */
  desc: string
  /** 是否**当前版本真的会读**这个键。false = 改了不生效。 */
  live: boolean
}

export const CONFIG_KEY_INFO: Record<string, ConfigKeyInfo> = {
  claim_ttl_days: { desc: '认领后超期自动退回「未处置」的时限（天）', live: true },
  auto_fixed_k_default: { desc: '连续 N 次回归通过后自动置「已修复」（次，取值 1–2）', live: true },
  rollup_late_k_h: { desc: '整点汇总回填最近 N 个已完成小时（小时）', live: true },
  keyword_search_days: { desc: '关键词检索回溯天数（天）', live: true },
  trace_query_timeout_ms: { desc: '链路查询超时（毫秒）', live: true },
  metric_agg_cache_ttl_s: { desc: '指标聚合结果的进程内缓存时长（秒，≤0 表示不缓存）', live: true },
  metric_agg_timeout_ms: { desc: '指标聚合查询超时（毫秒）', live: true },
  trace_judge_purge_days: { desc: '判定状态保留天数，超期清理（天）', live: true },

  cluster_window_days: { desc: '聚类去重窗口（天）', live: false },
  llm_call_observe_window_min: { desc: 'LLM 调用观测窗口（分钟）', live: false },
  llm_call_observe_threshold: { desc: 'LLM 调用观测阈值', live: false },
  trace_judge_window_s: { desc: '链路判定窗口（秒）', live: false },
  trace_judge_grace_s: { desc: '链路判定宽限期（秒）', live: false },
}

/** 未知键返回 null（键集非闭合），由调用方决定兜底文案。 */
export function configKeyInfo(key: string): ConfigKeyInfo | null {
  return CONFIG_KEY_INFO[key] ?? null
}

/** 页面上那一行灰字。未知键给空串（不制造噪音）。 */
export function configKeyDesc(key: string): string {
  const info = configKeyInfo(key)
  if (!info) return ''
  return info.live ? info.desc : `${info.desc} · 当前版本未读取，改动不生效`
}

/** 该键说明是否要按「未生效」样式显示（灰 + 警示色）。 */
export function configKeyIsDead(key: string): boolean {
  const info = configKeyInfo(key)
  return info != null && !info.live
}
