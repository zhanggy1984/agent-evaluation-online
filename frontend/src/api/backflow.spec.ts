// api/backflow.ts 契约测试：11 个导出逐个断言 **HTTP 方法 / 路径 / 查询串 / 请求体**。
// 这是前后端契约的前端侧护栏，与后端 test_backflow* 的响应形状断言配对——两边各钉一半。
// 手法：stub 全局 fetch，经真实 client.api 跑一遍（不 mock 模块），这样连
// `/api/v1` 前缀、Content-Type、Authorization 注入这些 client 侧行为也一并被固定住。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  backflowClusterDetail, backflowClusters, backflowOverview, batchResolve, claimCluster,
  fixedReview, ignoreCluster, linkInvalidate, linkRequeue, needsReviewResolve, reopenCluster,
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

describe('处置写面（viewer 可触达）', () => {
  it('claimCluster：POST 且请求体含 fix_version/k/note', async () => {
    const body = { fix_version: '2026.09.10-r1', k: 3, note: '已定位' }
    await claimCluster(7, body)
    const c = only()
    expect(c.method).toBe('POST')
    expect(c.url).toBe('/api/v1/backflow/clusters/7/claim')
    expect(c.body).toEqual(body)
  })

  it('ignoreCluster：POST 无请求体（不传 undefined body）', async () => {
    await ignoreCluster(7)
    const c = only()
    expect(c.method).toBe('POST')
    expect(c.url).toBe('/api/v1/backflow/clusters/7/ignore')
    expect(c.body).toBeUndefined()
  })

  it('reopenCluster：缺省 note 归一为显式 null（非 undefined 键缺失）', async () => {
    await reopenCluster(7)
    expect(only().body).toEqual({ note: null })
    await reopenCluster(7, '误判')
    expect(calls[1].body).toEqual({ note: '误判' })
  })

  it('fixedReview：approve 布尔原样透传（false 不可被吞成缺省）', async () => {
    await fixedReview(7, false)
    expect(only().body).toEqual({ approve: false })
  })

  it('needsReviewResolve：action 与 note 同送', async () => {
    await needsReviewResolve(7, 'escalated')
    const c = only()
    expect(c.url).toBe('/api/v1/backflow/clusters/7/needs-review-resolve')
    expect(c.body).toEqual({ action: 'escalated', note: null })
  })

  it('batchResolve：缺省 action = reopen_cluster（与后端缺省一致）', async () => {
    await batchResolve(9)
    const c = only()
    expect(c.url).toBe('/api/v1/backflow/needs-review-batches/9/resolve')
    expect(c.body).toEqual({ action: 'reopen_cluster' })
    await batchResolve(9, 'escalated')
    expect(calls[1].body).toEqual({ action: 'escalated' })
  })
})

describe('admin 写面', () => {
  it('linkInvalidate：POST /backflow/links/{id}/invalidate，reason 归一为 null', async () => {
    await linkInvalidate(3)
    const c = only()
    expect(c.method).toBe('POST')
    expect(c.url).toBe('/api/v1/backflow/links/3/invalidate')
    expect(c.body).toEqual({ reason: null })
    await linkInvalidate(3, 'offline_cap_gap')
    expect(calls[1].body).toEqual({ reason: 'offline_cap_gap' })
  })

  it('linkRequeue：POST 无请求体（增量锚在后端，不由前端传）', async () => {
    await linkRequeue(3)
    const c = only()
    expect(c.method).toBe('POST')
    expect(c.url).toBe('/api/v1/backflow/links/3/requeue')
    expect(c.body).toBeUndefined()
  })
})

describe('client 侧共性（11 个端点共享）', () => {
  it('全部经 /api/v1 前缀且 Content-Type 为 JSON', async () => {
    await backflowOverview()
    await linkRequeue(1)
    for (const c of calls) {
      expect(c.url.startsWith('/api/v1/backflow/')).toBe(true)
      expect(c.headers['Content-Type']).toBe('application/json')
    }
  })

  it('登录后自动注入 Bearer（写面鉴权不受本模块控制但依赖它）', async () => {
    localStorage.setItem('obs_access', 'tok-abc')
    await linkRequeue(1)
    expect(only().headers.Authorization).toBe('Bearer tok-abc')
  })

  it('无 token 时不发 Authorization 头（不出现 Bearer undefined）', async () => {
    await backflowOverview()
    expect(only().headers.Authorization).toBeUndefined()
  })
})
