// auth API（detail §8.1）：登录成功后保存 token + user 到 localStorage；登出尽力 revoke 会话。
import { api, clearAuth, saveAuth } from './client'
import type { TokenResponse } from './types'

export async function login(username: string, password: string): Promise<TokenResponse> {
  const t = await api<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }, false) // 登录本身不需要带 Bearer
  saveAuth(t)
  localStorage.setItem('obs_user', JSON.stringify(t.user))
  return t
}

export async function logout(): Promise<void> {
  // §8.1 logout = revoke 当前 refresh 会话。尽力而为：失败也照样清本地——
  // 未吊销的 refresh 靠 7d 过期兜底，access 15min 短效自愈。
  const refresh = localStorage.getItem('obs_refresh')
  if (refresh) {
    try {
      await api<unknown>('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refresh }),
      })
    } catch {
      /* 忽略：本地已清，短效 token 自动过期 */
    }
  }
  clearAuth()
}
