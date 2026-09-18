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

import { listTraces } from './traces'

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
