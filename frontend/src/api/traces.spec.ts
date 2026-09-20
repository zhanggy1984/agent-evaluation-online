// P1-11 补测：listTraces 的**参数透传**（真取 URL，不 mock 本模块）。
//
// 为什么单独立这个文件：TracesView.spec.ts 是 `vi.mock('../api/traces')` 的 ——
// 它只能证明「组件把 status 传给了 listTraces」，**结构性地证明不了「listTraces 把它发出去」**。
// 2026-09-18 真机实测正是断在这一层：组件传参正确、mock 测试全绿，而实际请求是
//   /api/v1/traces?interface=...&page=1&page_size=20   ← 没有 status，过滤静默失效。
// 类型系统也没拦住：TraceQuery 当时没有 status 字段，但 `const q = {..., status}` 因
// 「先赋值给变量再传参」绕过了「新鲜对象字面量多余属性检查」。
// ⇒ 本文件的存在意义 = 把「参数真的进了 URL」钉死在最外层。
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMock = vi.hoisted(() => vi.fn())
vi.mock('./client', () => ({ api: apiMock }))

import { listTraces, traceDetail, traceLogs } from './traces'

/** 取第 n 次调用传给 api() 的 path（第 0 个实参） */
const pathOf = (n = 0): string => apiMock.mock.calls[n][0] as string

describe('P1-11 listTraces 参数透传', () => {
  beforeEach(() => { apiMock.mockReset(); apiMock.mockResolvedValue({ items: [], total: 0 }) })

  it('status 必须进 URL（曾因类型漏洞静默丢失，见文件头）', async () => {
    await listTraces({ interface: 'POST /api/chat/{id}', status: 'error' })
    expect(pathOf()).toContain('status=error')
    // interface 与 status **并存**，不互相顶替
    expect(pathOf()).toContain('interface=POST+%2Fapi%2Fchat%2F%7Bid%7D')
  })

  it('status=timeout 同样透传（值域不止 error）', async () => {
    await listTraces({ status: 'timeout' })
    expect(pathOf()).toContain('status=timeout')
  })

  it('不传 status → URL 里不出现该参数（不能退化成空串参数的静默查询）', async () => {
    await listTraces({ interface: 'GET /api/rules' })
    expect(pathOf()).not.toContain('status')
  })

  it('status 与既有筛选并列时一个都不丢（防只补一个新的就挤掉旧的）', async () => {
    await listTraces({ trace_id: 't-1', agent: 'cc', interface: 'x', status: 'error', page: 2, page_size: 20 })
    const p = pathOf()
    for (const kv of ['trace_id=t-1', 'agent=cc', 'interface=x', 'status=error', 'page=2', 'page_size=20']) {
      expect(p).toContain(kv)
    }
  })
})

describe('P1-10 后半（2026-09-20）listTraces 时间窗透传', () => {
  beforeEach(() => { apiMock.mockReset(); apiMock.mockResolvedValue({ items: [], total: 0 }) })

  it('start_ts 必须进 URL（与 status 同形：漏一行就静默回退到后端默认窗，UI 上毫无征兆）', async () => {
    await listTraces({ start_ts: 1750000000000 })
    expect(pathOf()).toContain('start_ts=1750000000000')
  })

  it('不传 start_ts → URL 里不出现该参数（缺省由后端 keyword_search_days 兜底，不能退化成空串）', async () => {
    await listTraces({ agent: 'cc' })
    expect(pathOf()).not.toContain('start_ts')
  })

  it('start_ts 与既有筛选并列时一个都不丢', async () => {
    await listTraces({
      trace_id: 't-1', keyword: 'kw', agent: 'cc', interface: 'x',
      status: 'error', start_ts: 1750000000000, page: 1, page_size: 20,
    })
    const p = pathOf()
    for (const kv of [
      'trace_id=t-1', 'keyword=kw', 'agent=cc', 'interface=x',
      'status=error', 'start_ts=1750000000000', 'page=1', 'page_size=20',
    ]) {
      expect(p).toContain(kv)
    }
  })
})

// 日志正文放行（2026-09-20，用户拍板）。三条一组：第 1 条钉「要开的那一处确实开了」，
// 第 2/3 条钉「不该开的两处**没**开」—— 防的是后续「既然是正文面，那详情也一起开吧」
// 式的顺手扩面。详情/列表按后端 docstring ① 还是**检索面**总闸，而这两页根本没有
// input/output 的渲染点（详情列只有 seq/节点/接口/model/usage/时间/耗时/状态）。
describe('2026-09-20 日志正文放行：只开 /logs 一处', () => {
  beforeEach(() => { apiMock.mockReset(); apiMock.mockResolvedValue({ items: [], total: 0 }) })

  it('日志请求必须带 body_search=true（不带则后端序列化前把 log_message 置 None，页面只剩占位文案）', async () => {
    await traceLogs('cc', 't-1', 1, 50)
    expect(pathOf()).toContain('body_search=true')
  })

  it('详情请求不带 body_search（本页无 input/output 渲染点，开了是白放开正文面）', async () => {
    await traceDetail('cc', 't-1')
    expect(pathOf()).not.toContain('body_search')
  })

  it('列表请求不带 body_search（它同时是检索面总闸：multi_match fields 随开关收窄）', async () => {
    await listTraces({ agent: 'cc' })
    expect(pathOf()).not.toContain('body_search')
  })
})
