// API 客户端：自动带 Bearer access；401 时用 refresh 刷新一次后重试，仍失败清登录态回 /login。
// 约定（本批实现决定，detail 修订记录补记）：token 存 localStorage，键 obs_access/obs_refresh；
// Authorization header = `Bearer <access>`。
const ACCESS_KEY = 'obs_access'
const REFRESH_KEY = 'obs_refresh'
export const USER_KEY = 'obs_user'

function read(key: string): string | null {
  return localStorage.getItem(key)
}

function write(key: string, v: string): void {
  localStorage.setItem(key, v)
}

// refresh 失败（终局 401）→ 全局广播，main.ts 监听后回 /login（api 层不 import router 防环）
export const AUTH_EXPIRED_EVENT = 'obs:auth-expired'

export function emitAuthExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
}

export function clearAuth(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
}

export function readStoredUser(): { username: string; role: string } | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    const u = JSON.parse(raw) as { username: string; role: string }
    return u
  } catch {
    return null
  }
}

export function saveAuth(t: { access_token: string; refresh_token: string }): void {
  write(ACCESS_KEY, t.access_token)
  write(REFRESH_KEY, t.refresh_token)
}

export function accessToken(): string | null {
  return read(ACCESS_KEY)
}

// 语言无关的错误载荷：后端统一 {code, message}（detail §8.9）
export class ApiError extends Error {
  code: string
  status: number
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request(path: string, init: RequestInit = {}, withAuth = true): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }
  if (withAuth) {
    const tok = accessToken()
    if (tok) headers['Authorization'] = `Bearer ${tok}`
  }
  return fetch(`/api/v1${path}`, { ...init, headers })
}

async function parse(resp: Response): Promise<unknown> {
  if (resp.status === 204) return null
  const text = await resp.text()
  return text ? JSON.parse(text) : null
}

// 401 时单次 refresh 后重试；并发请求共享同一刷新 promise，防重放风暴
let refreshPromise: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  const refresh = read(REFRESH_KEY)
  if (!refresh) return false
  const resp = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!resp.ok) return false
  const t = (await resp.json()) as { access_token: string; refresh_token: string }
  saveAuth(t)
  return true
}

export async function api<T>(path: string, init: RequestInit = {}, withAuth = true): Promise<T> {
  let resp = await request(path, init, withAuth)
  if (resp.status === 401 && withAuth) {
    refreshPromise = refreshPromise ?? doRefresh().finally(() => {
      refreshPromise = null
    })
    if (await refreshPromise) {
      resp = await request(path, init, withAuth) // 重试一次
    }
  }
  if (!resp.ok) {
    let code = 'UNKNOWN'
    let message = `HTTP ${resp.status}`
    try {
      const body = (await resp.json()) as { code?: string; message?: string }
      if (body.code) code = body.code
      if (body.message) message = body.message
    } catch {
      /* 非 JSON 错误体：保底用状态码 */
    }
    if (resp.status === 401) {
      clearAuth()
      emitAuthExpired() // 广播 → main 回 /login
    }
    throw new ApiError(resp.status, code, message)
  }
  return (await parse(resp)) as T
}
