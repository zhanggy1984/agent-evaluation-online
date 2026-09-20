// 前端分页（批 47 / 任务 #44）：/interfaces、/anomalies、/llm-failures 三页共用的
// **每页条数**与**切片助手**。
//
// ⚠️ 为什么是前端分页而不是后端 page/page_size：这三页的数据源是 `metrics/*` 的固定
// top-N 聚合（接口页 terms size=50、异常/LLM 失败页 size≤100），**数据在到达前端时就
// 已被后端截断**。再请求 page/page_size 只会翻这同一批 top-N，反而多出一层「截断 + 分页」
// 口径叠加的歧义（用户会把「翻不到第 6 页」读成「后端只有 5 页」）。
//
// 常量放这里而不是各页各写一份：同一个「每页 20」抄进四个文件，改一处漏三处的症状是
// **页数对不上但没有任何判据会红**（与 CSS 逐列定宽漏改编号同型）。
export const PAGE_SIZE = 20

/** 取第 page 页（1 起）的行。越界返回空数组，不抛错、不兜底回第 1 页。 */
export function slicePage<T>(rows: T[], page: number): T[] {
  const start = (page - 1) * PAGE_SIZE
  return rows.slice(start, start + PAGE_SIZE)
}

/** 总页数（至少 1 —— 0 条也显示「1 / 1」而不是「1 / 0」）。 */
export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / PAGE_SIZE))
}
