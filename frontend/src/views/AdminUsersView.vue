<script setup lang="ts">
// 系统管理 · 账号页（T-3.12 批 1 / detail §8.6）：列表 / 建号 / 改角色 / 启停。
// 禁用与重置口令都会**撤销该用户全部未撤销会话**（后端 §8.6；即时生效机制 = user.status
// + user_session 两半，不是文档旧文里的 token version）。
// 自锁防护在后端：停用自己 / 改自己角色 → 400。
import { onMounted, ref } from 'vue'

import { adminCreateUser, adminUpdateUser, adminUsers } from '../api/admin'
import { ApiError, readStoredUser } from '../api/client'
import type { AdminUserOut } from '../api/types'

const me = readStoredUser()
const rows = ref<AdminUserOut[]>([])
const loading = ref(false)
const errorMsg = ref('')
const notice = ref('')

const form = ref({ username: '', password: '', display_name: '', role: 'viewer' })
const submitting = ref(false)
const busyId = ref<number | null>(null)

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    rows.value = await adminUsers()
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `账号读取失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  submitting.value = true
  errorMsg.value = ''
  notice.value = ''
  try {
    const created = await adminCreateUser({
      username: form.value.username.trim(),
      password: form.value.password,
      display_name: form.value.display_name.trim() || null,
      role: form.value.role,
    })
    notice.value = `已创建 ${created.username}（${created.role}）`
    form.value = { username: '', password: '', display_name: '', role: 'viewer' }
    await load()
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `创建失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    submitting.value = false
  }
}

// 只传变更字段（字段缺省 = 不修改，不是"清空"）
async function patch(u: AdminUserOut, body: Record<string, unknown>): Promise<void> {
  busyId.value = u.id
  errorMsg.value = ''
  notice.value = ''
  try {
    const updated = await adminUpdateUser(u.id, body)
    const idx = rows.value.findIndex((r) => r.id === u.id)
    if (idx >= 0) rows.value[idx] = updated
    notice.value = `${updated.username} 已更新（status=${updated.status}）`
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `更新失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    busyId.value = null
  }
}

function resetPassword(u: AdminUserOut): void {
  const pw = window.prompt(`为 ${u.username} 设置新口令（8~64 位；将撤销其全部会话）`) || ''
  if (!pw) return
  if (pw.length < 8 || pw.length > 64) {
    errorMsg.value = '口令长度需 8~64 位'
    return
  }
  void patch(u, { password: pw })
}

onMounted(() => void load())
</script>

<template>
  <div>
    <h2>系统管理 · 账号</h2>
    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-if="notice" class="ok">{{ notice }}</p>

    <p v-if="loading">加载中…</p>
    <!-- P2-22（2026-09-18）：同 AdminConfigsView —— 原先裸 <table class="tbl">，
         而 .tbl 零规则，表格无任何样式。按全仓惯例改 .panel 包裹。 -->
    <div v-else class="panel">
      <table>
        <thead>
          <tr>
            <th>用户名</th>
            <th>显示名</th>
            <th>角色</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in rows" :key="u.id">
            <td>
              <code>{{ u.username }}</code>
              <span v-if="me?.username === u.username" class="hint">（我）</span>
            </td>
            <td>{{ u.display_name || '—' }}</td>
            <td>
              <select
                :value="u.role"
                :disabled="busyId === u.id"
                @change="patch(u, { role: ($event.target as HTMLSelectElement).value })"
              >
                <option value="viewer">viewer</option>
                <option value="admin">admin</option>
              </select>
            </td>
            <td>{{ u.status === 1 ? '启用' : '停用' }}</td>
            <td>
              <button :disabled="busyId === u.id" @click="patch(u, { status: u.status === 1 ? 0 : 1 })">
                {{ u.status === 1 ? '停用' : '启用' }}
              </button>
              <button :disabled="busyId === u.id" @click="resetPassword(u)">重置口令</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3>新建账号</h3>
    <!-- P2-22（2026-09-18）：此处原为 class="tbl" —— 表单跨语义复用了表格的类名，
         且 .tbl 本身零规则。一并去掉，避免留下「有类名、查不到规则」的悬空类。 -->
    <form @submit.prevent="submit">
      <label>用户名 <input v-model="form.username" required maxlength="64" /></label>
      <label>口令 <input v-model="form.password" type="password" required minlength="8" maxlength="64" /></label>
      <label>显示名 <input v-model="form.display_name" maxlength="64" /></label>
      <label>
        角色
        <select v-model="form.role">
          <option value="viewer">viewer</option>
          <option value="admin">admin</option>
        </select>
      </label>
      <button :disabled="submitting" type="submit">创建</button>
    </form>
    <p class="hint">
      口令最小规则 = 长度 8~64（不做复杂度要求）。停用/改口令即时生效：该用户现有会话全部失效。
    </p>
  </div>
</template>
