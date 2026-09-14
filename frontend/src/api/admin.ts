// admin 系统管理 API（T-3.12 批 1 / detail §8.6）：配置管理 + 账号管理，全部 admin-only。
// 后端 require_admin 二次鉴权（403 ERR_AUTH_0002）；前端按 role 隐藏菜单只是 UX，403 才是权威
// （与 backflow.ts 同一"双保险"口径）。
import { api } from './client'
import type {
  AdminConfigItem,
  AdminUserOut,
} from './types'

// ---------- 配置（§8.6） ----------

// agent 缺省 = 全局键（v1 生效键全量，缺行键按 seed 默认回显 is_default=true）
export function adminConfigs(agentId?: number): Promise<AdminConfigItem[]> {
  const suffix = agentId === undefined ? '' : `?agent=${agentId}`
  return api<AdminConfigItem[]>(`/admin/configs${suffix}`)
}

export interface ConfigPutBody {
  key: string
  value: unknown
  agent_id?: number
}

// 写入后后端 version +1 并落 config_change 审计；响应即新值（无需重拉）
export function adminPutConfig(body: ConfigPutBody): Promise<AdminConfigItem> {
  return api<AdminConfigItem>('/admin/configs', { method: 'PUT', body: JSON.stringify(body) })
}

// ---------- 账号（§8.6） ----------

export function adminUsers(): Promise<AdminUserOut[]> {
  return api<AdminUserOut[]>('/admin/users')
}

export interface UserCreateBody {
  username: string
  password: string
  display_name?: string | null
  role: string
}

export function adminCreateUser(body: UserCreateBody): Promise<AdminUserOut> {
  return api<AdminUserOut>('/admin/users', { method: 'POST', body: JSON.stringify(body) })
}

export interface UserUpdateBody {
  display_name?: string | null
  role?: string
  status?: number
  password?: string
}

// 字段缺省 = 不修改；status=0 或改口令都会撤销该用户全部未撤销会话（后端 §8.6）
export function adminUpdateUser(uid: number, body: UserUpdateBody): Promise<AdminUserOut> {
  return api<AdminUserOut>(`/admin/users/${uid}`, { method: 'PUT', body: JSON.stringify(body) })
}
