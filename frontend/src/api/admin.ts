// admin 系统管理 API（T-3.12 批 1 / detail §8.6）：配置管理 + 账号管理，全部 admin-only。
// 后端 require_admin 二次鉴权（403 ERR_AUTH_0002）；前端按 role 隐藏菜单只是 UX，403 才是权威
// （与 backflow.ts 同一"双保险"口径）。
import { api } from './client'
import type {
  AdminAgentCredentialOut,
  AdminAgentHealthOut,
  AdminAgentOut,
  AdminConfigItem,
  AdminInterfaceListOut,
  AdminInterfaceOut,
  AdminUserOut,
  InterfaceUpdateBody,
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

// ---------- agent 与接口字典（§8.5，T-3.12 批 2a-1） ----------

// 读 MySQL 字典面（不是 ES）——零流量/已停用的 agent 也在这里，这是它与 /metrics/agents 的区别
export function adminAgents(): Promise<AdminAgentOut[]> {
  return api<AdminAgentOut[]>('/admin/agents')
}

// 无 body：后端翻转 enable（停用仅停回流生成与展示，消费不停——防数据黑洞）
export function adminToggleAgent(agentId: number): Promise<AdminAgentOut> {
  return api<AdminAgentOut>(`/admin/agents/${agentId}/toggle`, { method: 'POST' })
}

export function adminAgentInterfaces(agentId: number): Promise<AdminInterfaceListOut> {
  return api<AdminInterfaceListOut>(`/admin/agents/${agentId}/interfaces`)
}

// agent 上报健康卡（§8.5）：读 ES 心跳 doc——last_seen_ts 为 null = 查询窗内无心跳（前端文案不再断言「未接入 SDK」）
export function adminAgentHealth(agentId: number): Promise<AdminAgentHealthOut> {
  return api<AdminAgentHealthOut>(`/admin/agents/${agentId}/health`)
}

// Kafka 上报凭证**脱敏**读面（§8.5，批 2b）：后端连 secret_cipher 这一列都不读，响应无 secret 字段。
// credential 为 null = 尚未发放凭证（合法态），不是「agent 不存在」（那是 400）。
// ⚠️ 本批**无 rotate**——三个执行动作全在 infra，已下移 T-5.3；此处也不留轮换入口占位。
export function adminAgentCredential(agentId: number): Promise<AdminAgentCredentialOut> {
  return api<AdminAgentCredentialOut>(`/admin/agents/${agentId}/credential`)
}

// 人工补标：llm=1 会连带清 llm_suspect（疑似漏标告警由人工确认解除）；llm_source 只接受 manual
export function adminPutInterface(
  ifaceId: number,
  body: InterfaceUpdateBody,
): Promise<AdminInterfaceOut> {
  return api<AdminInterfaceOut>(`/admin/interfaces/${ifaceId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}
