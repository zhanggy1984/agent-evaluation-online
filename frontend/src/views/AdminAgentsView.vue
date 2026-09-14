<script setup lang="ts">
// 系统管理 · Agent 页（T-3.12 批 2a-1 / detail §8.5）：agent 清单 + 启停 + 接口字典人工补标。
//
// ⚠️ 与「接口」页（§8.3 看板）的区别：那是 **ES 观测面**（近 7d 有流量的 agent 名），
// 零流量 / 已停用的 agent 在其中**完全不可见**；本页读 **MySQL 字典面**，因此能看到
// 「接入但掉线」与「本来就没接」的差别。
// ⚠️ 本页**没有**凭证查看/轮换区（§8.5 凭证两端点属批 2b，未实现）——不留占位，
// 免得后人把占位读成「功能在、只是没数据」。
// ⚠️ 接口串**不可改**（唯一键列 + 后端入参无该字段）；本页只改 llm / llm_source / body_search。
import { onMounted, ref } from 'vue'

import { adminAgentInterfaces, adminAgents, adminPutInterface, adminToggleAgent } from '../api/admin'
import { ApiError } from '../api/client'
import type { AdminAgentOut, AdminInterfaceOut } from '../api/types'

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
  ifaceLoading.value = true
  errorMsg.value = ''
  try {
    const res = await adminAgentInterfaces(a.id)
    ifaces.value = res.items
    ifaceTruncated.value = res.truncated
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `接口读取失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    ifaceLoading.value = false
  }
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
  </div>
</template>
