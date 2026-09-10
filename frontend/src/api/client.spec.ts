// api/client.ts 单测：登录态读写、错误契约、**401 刷新单飞**。
// 单飞（refreshPromise 复用）是并发守卫：列表页一屏可能同时发多个请求，若每个 401 都各自
// 打一次 refresh，会拿同一 refresh_token 重放多次——后端若做一次性轮换就会连锁失败。
// 该分支此前零覆盖，且失效时**不会**有测试变红（各自刷新在单请求下表现一致），故必须专测。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AUTH_EXPIRED_EVENT, ApiError, accessToken, api, clearAuth, readStoredUser, saveAuth,
} from './client'

let fetchMock: ReturnType<typeof vi.fn>
let attempts: Record<string, number>

/** url → 依次返回的状态/载荷；'*' 为兜底规则 */
function stub(routes: Record<string, (n: number) => Response>) {
  attempts = {}
  fetchMock = vi.fn(async (url: string) => {
    const n = (attempts[url] = (attempts[url] ?? 0) + 1)
    const rule = routes[url] ?? routes['*']
    return rule ? rule(n) : new Response('{}', { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const refreshCalls = () => fetchMock.mock.calls.filter(c => String(c[0]).includes('/auth/refresh'))

/** 期望抛错并取回错误对象（`.catch(e => e)` 在 strict 下推为 unknown，无法读 status/code） */
async function caught(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p
  } catch (e) {
    return e as ApiError
  }
  throw new Error('预期请求抛错，但成功返回')
}

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('readStoredUser', () => {
  it('无键 → null', () => {
    expect(readStoredUser()).toBeNull()
  })

  it('坏 JSON → null（不抛，登录态损坏不炸路由守卫）', () => {
    localStorage.setItem('obs_user', '{not json')
    expect(readStoredUser()).toBeNull()
  })

  it('正常 → 解出 username/role', () => {
    localStorage.setItem('obs_user', JSON.stringify({ username: 'admin', role: 'admin' }))
    expect(readStoredUser()).toEqual({ username: 'admin', role: 'admin' })
  })
})

describe('saveAuth / accessToken / clearAuth', () => {
  it('saveAuth 落 access+refresh，clearAuth 三键全清', () => {
    saveAuth({ access_token: 'a1', refresh_token: 'r1' })
    expect(accessToken()).toBe('a1')
    localStorage.setItem('obs_user', '{}')
    clearAuth()
    expect(accessToken()).toBeNull()
    expect(localStorage.getItem('obs_refresh')).toBeNull()
    expect(localStorage.getItem('obs_user')).toBeNull()
  })
})

describe('ApiError', () => {
  it('带 status/code/message，且是 Error 实例（可被 catch 分支识别）', () => {
    const e = new ApiError(409, 'ERR_CLUSTER_0002', '并发处置冲突')
    expect(e).toBeInstanceOf(Error)
    expect([e.status, e.code, e.message]).toEqual([409, 'ERR_CLUSTER_0002', '并发处置冲突'])
    expect(e.name).toBe('Error')
  })
})

describe('api 正常/错误路径', () => {
  it('204 无体 → null（不是 JSON.parse 崩）', async () => {
    stub({ '*': () => new Response(null, { status: 204 }) })
    await expect(api('/x', {}, false)).resolves.toBeNull()
  })

  it('错误体 {code,message} 透传进 ApiError', async () => {
    stub({ '*': () => json({ code: 'ERR_CLUSTER_0002', message: '并发处置冲突' }, 409) })
    const err = await caught(api('/x', {}, false))
    expect(err).toBeInstanceOf(ApiError)
    expect([err.status, err.code, err.message]).toEqual([409, 'ERR_CLUSTER_0002', '并发处置冲突'])
  })

  it('非 JSON 错误体 → 保底 UNKNOWN + HTTP <status>（不二次抛解析错）', async () => {
    stub({ '*': () => new Response('<html>502</html>', { status: 502 }) })
    const err = await caught(api('/x', {}, false))
    expect([err.status, err.code, err.message]).toEqual([502, 'UNKNOWN', 'HTTP 502'])
  })

  it('withAuth=false 不发 Authorization，401 也不触发刷新', async () => {
    localStorage.setItem('obs_refresh', 'r1')
    stub({ '*': () => json({ code: 'ERR_AUTH_0001', message: '未登录' }, 401) })
    await expect(api('/auth/login', {}, false)).rejects.toBeInstanceOf(ApiError)
    expect(refreshCalls()).toHaveLength(0)
  })
})

describe('401 刷新与单飞', () => {
  it('刷新成功后原请求重试一次，且新 token 已落库', async () => {
    localStorage.setItem('obs_refresh', 'r-old')
    stub({
      '/api/v1/auth/refresh': () => json({ access_token: 'a-new', refresh_token: 'r-new' }),
      '*': n => (n === 1 ? json({}, 401) : json({ ok: true })),
    })
    await expect(api('/backflow/overview')).resolves.toEqual({ ok: true })
    expect(refreshCalls()).toHaveLength(1)
    expect(accessToken()).toBe('a-new')
    expect(localStorage.getItem('obs_refresh')).toBe('r-new')
  })

  it('**并发 401 只刷新一次**：多个在飞请求共享同一 refresh promise', async () => {
    localStorage.setItem('obs_refresh', 'r-old')
    stub({
      '/api/v1/auth/refresh': () => json({ access_token: 'a-new', refresh_token: 'r-new' }),
      '*': n => (n === 1 ? json({}, 401) : json({ ok: true })),
    })
    const [r1, r2, r3] = await Promise.all([
      api('/a'), api('/b'), api('/c'),
    ])
    expect([r1, r2, r3]).toEqual([{ ok: true }, { ok: true }, { ok: true }])
    expect(refreshCalls()).toHaveLength(1)  // 关键断言：不是 3
  })

  it('刷新完成后单飞状态复位，下一轮 401 仍会再刷（不粘死）', async () => {
    localStorage.setItem('obs_refresh', 'r-old')
    stub({
      '/api/v1/auth/refresh': () => json({ access_token: 'a-new', refresh_token: 'r-new' }),
      '*': n => (n % 2 === 1 ? json({}, 401) : json({ ok: true })),
    })
    await api('/a')            // 第 1 次 401 → 刷新 → 重试成功
    await api('/a')            // 第 3 次 401 → 应再刷新一次
    expect(refreshCalls()).toHaveLength(2)
  })

  it('无 refresh_token → 不请求 refresh，清登录态并广播 auth-expired', async () => {
    stub({ '*': () => json({ code: 'ERR_AUTH_0001', message: '登录已过期' }, 401) })
    const onExpired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)

    const err = await caught(api('/backflow/overview'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(401)
    expect(refreshCalls()).toHaveLength(0)
    expect(onExpired).toHaveBeenCalledTimes(1)
    window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  })

  it('refresh 失败（后端拒）→ 广播 + 清态 + 抛原 401，不无限重试', async () => {
    localStorage.setItem('obs_refresh', 'r-bad')
    stub({
      '/api/v1/auth/refresh': () => json({}, 401),
      '*': () => json({ code: 'ERR_AUTH_0001', message: '登录已过期' }, 401),
    })
    const onExpired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)

    const err = await caught(api('/backflow/overview'))
    expect(err.status).toBe(401)
    expect(attempts['/api/v1/backflow/overview']).toBe(1)  // 只试原请求 1 次，未重试
    expect(onExpired).toHaveBeenCalledTimes(1)
    expect(accessToken()).toBeNull()
    window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  })

  it('重试后仍 401 → 不再二次刷新（每请求至多刷一次）', async () => {
    localStorage.setItem('obs_refresh', 'r-old')
    stub({
      '/api/v1/auth/refresh': () => json({ access_token: 'a-new', refresh_token: 'r-new' }),
      '*': () => json({ code: 'ERR_AUTH_0001', message: '仍过期' }, 401),
    })
    const err = await caught(api('/backflow/overview'))
    expect(err.status).toBe(401)
    expect(refreshCalls()).toHaveLength(1)
  })
})
