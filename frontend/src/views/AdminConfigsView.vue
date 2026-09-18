<script setup lang="ts">
// 系统管理 · 配置页（T-3.12 批 1 / detail §8.6）：**只做全局键**（agent 缺省）的读与写。
// ⚠️ 本页**没有** per-agent 编辑入口——词表 fallback_utterance（D19 wordlist_version 载体）
// 与 timeout_ms 已具备后端端点（PUT /admin/configs 带 agent_id），但 UI 尚未提供，改词表需直接调端点。
// 审计：后端落 config_change 行，但跨 cluster 的审计读面尚未实现（归 T-3.13），
// 故本页不提供"变更历史"视图，改词表后请勿在 UI 里找审计。
import { onMounted, ref } from 'vue'

import { adminConfigs, adminPutConfig } from '../api/admin'
import { ApiError } from '../api/client'
import type { AdminConfigItem } from '../api/types'
// 键说明（P0-3）：语义逐个回查后端读取点，非按键名猜；零读取点的键标「改动不生效」。
import { configKeyDesc, configKeyIsDead } from '../configLabels'

const items = ref<AdminConfigItem[]>([])
const loading = ref(false)
const errorMsg = ref('')
const notice = ref('')
// key → 编辑中的字符串值（数字键也按字符串编辑，提交时按原类型解析）
const drafts = ref<Record<string, string>>({})
const saving = ref<string>('')

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await adminConfigs()
    items.value = res
    drafts.value = Object.fromEntries(res.map((i) => [i.key, String(i.value)]))
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `配置读取失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    loading.value = false
  }
}

function isInt(v: unknown): boolean {
  return typeof v === 'number' && Number.isInteger(v)
}

// 提交：按**原值类型**解析（int 键 → Number；非数字输入给后端前先在前端拦一道，
// 后端 ERR_CONFIG_0001 仍是权威校验）
async function save(item: AdminConfigItem): Promise<void> {
  const raw = drafts.value[item.key] ?? ''
  let value: unknown = raw
  if (isInt(item.value)) {
    const n = Number(raw)
    if (!Number.isInteger(n)) {
      errorMsg.value = `${item.key} 需要整数，当前输入：${raw}`
      return
    }
    value = n
  }
  saving.value = item.key
  errorMsg.value = ''
  notice.value = ''
  try {
    const updated = await adminPutConfig({ key: item.key, value })
    const idx = items.value.findIndex((i) => i.key === item.key)
    if (idx >= 0) items.value[idx] = updated
    notice.value = `${item.key} 已保存：version → ${updated.version}（变更已落审计）`
  } catch (e) {
    if (e instanceof ApiError) errorMsg.value = `保存失败（${e.code}）：${e.message}`
    else throw e
  } finally {
    saving.value = ''
  }
}

onMounted(() => void load())
</script>

<template>
  <div>
    <h2>系统管理 · 配置</h2>
    <p class="hint">
      当前生效的配置键（全局）。写入后 <code>version</code> 自增并落 <code>config_change</code> 审计。
      词表 <code>fallback_utterance</code> 为 per-agent 键，每个 agent 各自维护版本。
    </p>
    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-if="notice" class="ok">{{ notice }}</p>
    <p v-if="loading">加载中…</p>
    <table v-else class="tbl">
      <thead>
        <tr>
          <th>键</th>
          <th>值</th>
          <th>version</th>
          <th>更新人 / 时间</th>
          <th />
        </tr>
      </thead>
      <tbody>
        <tr v-for="i in items" :key="i.key">
          <td>
            <code>{{ i.key }}</code>
            <div v-if="configKeyDesc(i.key)" class="key-desc" :class="{ dead: configKeyIsDead(i.key) }">
              {{ configKeyDesc(i.key) }}
            </div>
          </td>
          <td><input v-model="drafts[i.key]" :aria-label="i.key" /></td>
          <td>
            {{ i.version }}
            <span v-if="i.is_default" class="hint">（seed 默认，库内无行）</span>
          </td>
          <td class="hint">{{ i.updated_by || '—' }} / {{ i.updated_ts || '—' }}</td>
          <td>
            <button :disabled="saving === i.key" @click="save(i)">保存</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="hint">
      注：审计记录当前没有独立的查询入口，本页不展示变更历史。
    </p>
  </div>
</template>

<style scoped>
/* 键说明（P0-3）：键名是英文串，新手读不懂；说明按「能用到这个键时」写在键下方。
   .dead = 后端当前无读取点，改了不生效——用警示色，与普通说明区分开。 */
.key-desc {
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
  max-width: 320px;
  line-height: 1.4;
}

.key-desc.dead {
  color: var(--timeout);
}
</style>
