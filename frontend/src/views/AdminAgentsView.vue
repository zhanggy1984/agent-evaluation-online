<script setup lang="ts">
// 系统管理 · Agent 页（T-3.12 批 2a-1 / detail §8.5）：agent 清单 + 启停 + 接口字典人工补标。
//
// ⚠️ 与「接口」页（§8.3 看板）的区别：那是 **ES 观测面**（近 7d 有流量的 agent 名），
// 零流量 / 已停用的 agent 在其中**完全不可见**；本页读 **MySQL 字典面**，因此**两种 agent 都列得出来**。
// ⚠️ 但「列得出来」≠「分得清」：health 卡**无法区分**「接入后掉线」与「本来就没接」——两者都表现为
//    「查询窗内无心跳」（2026-09-14 订正：原注释写「能看到二者的差别」，说过头了）。
// ⚠️ 本页**没有**凭证查看/轮换区（§8.5 凭证两端点属批 2b，未实现）——不留占位，
// 免得后人把占位读成「功能在、只是没数据」。
// ⚠️ 接口串**不可改**（唯一键列 + 后端入参无该字段）；本页只改 llm / llm_source / body_search。
// ⚠️ 展开行内的「上报健康」读的是 **ES 心跳面**（第三个数据源），故与接口字典分开报错；
//    `last_seen_ts` 为空时文案只说「查询窗内无心跳上报」——**不再断言「未接入 SDK」**（2026-09-14 收窄）。
//    该判据（§9.1 `no_agent`）承载的是「窗内无心跳」，**它区分不了**「从未接入」与「曾接入但断联超窗」
//    （窗 = `keyword_search_days`）；把后者说成前者方向相反——前者是待办、后者是故障。
import { onMounted, ref } from 'vue'

import {
  adminAgentHealth,
  adminAgentInterfaces,
  adminAgents,
  adminPutInterface,
  adminToggleAgent,
} from '../api/admin'
import { ApiError } from '../api/client'
import type { AdminAgentHealthOut, AdminAgentOut, AdminInterfaceOut } from '../api/types'

const rows = ref<AdminAgentOut[]>([])
const loading = ref(false)
const errorMsg = ref('')
const notice = ref('')
const busyId = ref<number | null>(null)

// 展开行 = 该 agent 的接口字典（按需拉取，不预载全量）
const openId = ref<number | null>(null)
const ifaces = ref<AdminInterfaceOut[]>([])
const ifaceTruncated = ref(false)
const ifaceLoading = ref(false)
const ifaceBusyId = ref<number | null>(null)

// 展开行内的上报健康卡（ES 心跳面，与上面的 MySQL 字典面是两个数据源）
const health = ref<AdminAgentHealthOut | null>(null)
const healthLoading = ref(false)
const healthErr = ref('')

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    rows.value = await adminAgents()
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `agent 读取失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    loading.value = false
  }
}

async function toggle(a: AdminAgentOut): Promise<void> {
  busyId.value = a.id
  errorMsg.value = ''
  notice.value = ''
  try {
    const updated = await adminToggleAgent(a.id)
    const idx = rows.value.findIndex((r) => r.id === a.id)
    if (idx >= 0) rows.value[idx] = updated
    notice.value = `${updated.name} 已${updated.enable === 1 ? '启用' : '停用'}`
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `启停失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    busyId.value = null
  }
}

async function expand(a: AdminAgentOut): Promise<void> {
  if (openId.value === a.id) {
    openId.value = null
    return
  }
  openId.value = a.id
  ifaces.value = []
  ifaceTruncated.value = false
  health.value = null
  healthErr.value = ''
  ifaceLoading.value = true
  healthLoading.value = true
  errorMsg.value = ''
  // 接口字典（MySQL）与心跳（ES）是两个数据源，用 allSettled 各报各的错——
  // ES 查询超时不该让接口字典整块消失，反之亦然。
  const [ifaceRes, healthRes] = await Promise.allSettled([
    adminAgentInterfaces(a.id),
    adminAgentHealth(a.id),
  ])
  if (ifaceRes.status === 'fulfilled') {
    ifaces.value = ifaceRes.value.items
    ifaceTruncated.value = ifaceRes.value.truncated
  } else if (ifaceRes.reason instanceof ApiError) {
    errorMsg.value = `接口读取失败（${ifaceRes.reason.code}）：${ifaceRes.reason.message}`
  } else {
    throw ifaceRes.reason
  }
  if (healthRes.status === 'fulfilled') {
    health.value = healthRes.value
  } else if (healthRes.reason instanceof ApiError) {
    healthErr.value = `心跳读取失败（${healthRes.reason.code}）：${healthRes.reason.message}`
  } else {
    throw healthRes.reason
  }
  ifaceLoading.value = false
  healthLoading.value = false
}

function fmtTs(ts: number | null): string {
  return ts === null ? '—' : new Date(ts).toLocaleString()
}

// dropped 是 consumer **进程内累计**快照（重启归零），不是窗口增量 ⇒ 原样列出，不做任何求和
function fmtDropped(d: Record<string, number>): string {
  const keys = Object.keys(d)
  return keys.length === 0 ? '无' : keys.map((k) => `${k}=${d[k]}`).join('、')
}

// 只传变更字段（字段缺省 = 不修改）。llm=1 时后端连带清 llm_suspect。
async function patchIface(row: AdminInterfaceOut, body: Record<string, unknown>): Promise<void> {
  ifaceBusyId.value = row.id
  errorMsg.value = ''
  notice.value = ''
  try {
    const updated = await adminPutInterface(row.id, body)
    const idx = ifaces.value.findIndex((r) => r.id === row.id)
    if (idx >= 0) ifaces.value[idx] = updated
    notice.value = `${updated.interface} 已更新`
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `补标失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    ifaceBusyId.value = null
  }
}

function markLlm(row: AdminInterfaceOut): void {
  void patchIface(row, { llm: 1, llm_source: 'manual' })
}

onMounted(() => void load())
</script>

<template>
  <div>
    <h2>系统管理 · Agent</h2>
    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-if="notice" class="ok">{{ notice }}</p>

    <p v-if="loading">加载中…</p>
    <table v-else class="tbl">
      <thead>
        <tr>
          <th>Agent</th>
          <th>显示名</th>
          <th>来源</th>
          <th>回流白名单</th>
          <th>接口数</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="a in rows" :key="a.id">
          <tr>
            <td><code>{{ a.name }}</code></td>
            <td>{{ a.display_name || '—' }}</td>
            <td>{{ a.route_source }}</td>
            <td>{{ a.backflow_allow === 1 ? '允许' : '禁止' }}</td>
            <td>{{ a.interface_count }}</td>
            <td>{{ a.enable === 1 ? '启用' : '停用' }}</td>
            <td>
              <button :disabled="busyId === a.id" @click="toggle(a)">
                {{ a.enable === 1 ? '停用' : '启用' }}
              </button>
              <button :disabled="ifaceLoading" @click="expand(a)">
                {{ openId === a.id ? '收起接口' : '接口字典' }}
              </button>
            </td>
          </tr>
          <tr v-if="openId === a.id">
            <td colspan="7">
              <div class="health">
                <strong>上报健康</strong>
                <span v-if="healthLoading" class="hint">心跳查询中…</span>
                <span v-else-if="healthErr" class="err">{{ healthErr }}</span>
                <template v-else-if="health">
                  <span v-if="health.last_seen_ts === null" class="err">
                    查询窗内无心跳上报
                  </span>
                  <template v-else>
                    <span>最后上报 {{ fmtTs(health.last_seen_ts) }}</span>
                    <span>近 1 分钟上报 {{ health.report_1min }} 次</span>
                    <span>近 5 分钟上报 {{ health.report_5min }} 次</span>
                    <span>SDK 自报心跳 {{ health.sdk_connected ? '有' : '无' }}</span>
                    <span>
                      丢弃计数 {{ fmtDropped(health.dropped) }}
                      <em v-if="Object.keys(health.dropped).length" class="hint">
                        （进程内累计快照，重启归零）
                      </em>
                    </span>
                  </template>
                </template>
              </div>
              <p v-if="ifaceLoading">接口加载中…</p>
              <p v-else-if="ifaces.length === 0" class="hint">该 agent 暂无接口字典行。</p>
              <template v-else>
                <p v-if="ifaceTruncated" class="hint">
                  该 agent 的接口数超过单次上限（500），以下只列出前 500 条。
                </p>
                <table class="tbl">
                  <thead>
                    <tr>
                      <th>接口</th>
                      <th>方法</th>
                      <th>路径</th>
                      <th>LLM</th>
                      <th>来源</th>
                      <th>疑似漏标</th>
                      <th>正文检索</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="i in ifaces" :key="i.id">
                      <td><code>{{ i.interface }}</code></td>
                      <td>{{ i.method || '—' }}</td>
                      <td>{{ i.path || '—' }}</td>
                      <td>{{ i.llm === 1 ? '是' : '否' }}</td>
                      <td>{{ i.llm_source || '—' }}</td>
                      <td>
                        {{ i.llm_suspect === 1 ? '疑似' : '—' }}
                        <span v-if="i.llm_suspect === 1" class="hint">（确认后自动解除）</span>
                      </td>
                      <td>{{ i.body_search === 1 ? '开' : '关' }}</td>
                      <td>
                        <button
                          v-if="i.llm === 0"
                          :disabled="ifaceBusyId === i.id"
                          @click="markLlm(i)"
                        >
                          标为 LLM
                        </button>
                        <button
                          v-else
                          :disabled="ifaceBusyId === i.id"
                          @click="patchIface(i, { llm: 0 })"
                        >
                          取消 LLM
                        </button>
                        <button
                          :disabled="ifaceBusyId === i.id"
                          @click="patchIface(i, { body_search: i.body_search === 1 ? 0 : 1 })"
                        >
                          {{ i.body_search === 1 ? '关正文检索' : '开正文检索' }}
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </template>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <p class="hint">
      停用**仅停回流生成与展示，消费不停**（防数据黑洞）。接口串不可改——它是唯一键列；
      需要「换串」时请新增接口行，不要改旧的。人工「标为 LLM」会连带解除该行的「疑似漏标」。
    </p>

    <p class="hint">
      「上报健康」读 ES 心跳，时间窗与检索面同一个「回溯天数」配置；「丢弃计数」是 consumer
      **进程内累计值**（该进程重启即归零），且取的是最新一条心跳的快照、不是窗口增量——
      别把它当历史总丢弃数。
    </p>
  </div>
</template>
