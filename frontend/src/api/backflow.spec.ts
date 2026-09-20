// api/backflow.ts 契约测试：3 个**只读**导出逐个断言 **HTTP 方法 / 路径 / 查询串**。
// 这是前后端契约的前端侧护栏，与后端 test_backflow* 的响应形状断言配对——两边各钉一半。
// 手法：stub 全局 fetch，经真实 client.api 跑一遍（不 mock 模块），这样连
// `/api/v1` 前缀、Content-Type、Authorization 注入这些 client 侧行为也一并被固定住。
// ⚠️ 批 35-B：人工处置写面（8 个导出）已整体删除，原「处置写面 / admin 写面」两段随之删除。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  backflowClusterDetail, backflowClusters, backflowOverview,
} from './backflow'

interface Captured {
  url: string
  method: string
  headers: Record<string, string>
  body: unknown
}

let calls: Captured[] = []

function stubFetch(payload: unknown = {}) {
  calls = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    calls.push({
      url,
      method: init.method ?? 'GET',
      headers: (init.headers ?? {}) as Record<string, string>,
      body: init.body ? JSON.parse(init.body as string) : undefined,
    })
    return new Response(JSON.stringify(payload), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })
  }))
}

const only = () => {
  expect(calls).toHaveLength(1)
  return calls[0]
}

beforeEach(() => {
  localStorage.clear()
  stubFetch()
})

describe('读面', () => {
  it('backflowOverview：GET /backflow/overview 无查询串', async () => {
    await backflowOverview()
    const c = only()
    expect(c.method).toBe('GET')
    expect(c.url).toBe('/api/v1/backflow/overview')
  })

  it('backflowClusters：空查询对象不产出裸「?」', async () => {
    await backflowClusters({})
    expect(only().url).toBe('/api/v1/backflow/clusters')
  })

  it('backflowClusters：七个筛选/分页参数逐项进入查询串', async () => {
    await backflowClusters({
      agent: 'a-1', interface: 'POST /api/chat', layer: 'L1', status: 'open',
      watch: 'active', page: 2, page_size: 50,
    })
    const c = only()
    expect(c.url).toBe(
      '/api/v1/backflow/clusters?agent=a-1&interface=POST+%2Fapi%2Fchat&layer=L1'
      + '&status=open&watch=active&page=2&page_size=50',
    )
  })

  it('backflowClusters：空字符串参数被剔除（视为「全部」而非筛空值）', async () => {
    // 筛选下拉的「全部」项 value=''，若原样拼串会变成 layer= 传给后端
    await backflowClusters({ agent: '', layer: '', status: '', page: 1 })
    expect(only().url).toBe('/api/v1/backflow/clusters?page=1')
  })

  it('backflowClusters：page=0 被归一为「不发该参数」，交后端取默认', async () => {
    // page 是 1-based（视图 ref(1)，后端 `page = max(page, 1)`），0 非法。
    // qs 用真值判断过滤 → 0 被剔除 → 后端兜 default=1，等价于第一页，语义正确。
    // 钉住这点是为了防有人把 `if (params.page)` 改成 `?? ` 后发出 page=0 触发后端 max 改写。
    await backflowClusters({ page: 0 })
    expect(only().url).not.toContain('page=')
  })

  it('backflowClusterDetail：路径带 clusterId', async () => {
    await backflowClusterDetail(42)
    expect(only().url).toBe('/api/v1/backflow/clusters/42')
  })
})

describe('client 侧共性（3 个端点共享）', () => {
  it('全部经 /api/v1 前缀且 Content-Type 为 JSON', async () => {
    await backflowOverview()
    await backflowClusters({})
    await backflowClusterDetail(1)
    expect(calls).toHaveLength(3)
    for (const c of calls) {
      expect(c.url.startsWith('/api/v1/backflow/')).toBe(true)
      expect(c.headers['Content-Type']).toBe('application/json')
    }
  })

  it('登录后自动注入 Bearer', async () => {
    localStorage.setItem('obs_access', 'tok-abc')
    await backflowClusterDetail(1)
    expect(only().headers.Authorization).toBe('Bearer tok-abc')
  })

  it('无 token 时不发 Authorization 头（不出现 Bearer undefined）', async () => {
    await backflowOverview()
    expect(only().headers.Authorization).toBeUndefined()
  })
})
