<script setup lang="ts">
// 指标页共享筛选条（Q3/Q4/Q5 决策）：
// - {agent, window} 读写 useMetricFilter 模块级单例 → 切页/刷新保持，任一指标页改动即联动。
// - agent 下拉数据源 = GET /metrics/agents（动态实测）；空 = 全站。
// - 手动"刷新"按钮触发当前页重拉（总览另有 60s 自动刷新，见 OverviewView）。
import { onMounted } from 'vue'

import { useAgents } from '../composables/useAgents'
import { useMetricFilter, WINDOWS } from '../composables/useMetricFilter'

defineProps<{ loading: boolean }>()
defineEmits<{ (e: 'refresh'): void }>()

const { filter } = useMetricFilter()
const { agents, loading: agentsLoading, errorMsg: agentsError, load: loadAgents } = useAgents()

function pickAgent(v: string): void {
  filter.agent = v
}

function pickWindow(v: string): void {
  filter.window = v as typeof filter.window
}

function retryAgents(): void {
  void loadAgents(true)
}

onMounted(() => void loadAgents())
</script>

<template>
  <div class="panel bar">
    <div class="row">
      <label class="muted lab">agent</label>
      <select :value="filter.agent" class="sel" @change="pickAgent(($event.target as HTMLSelectElement).value)">
        <option value="">全站</option>
        <option v-for="a in agents" :key="a" :value="a">{{ a }}</option>
      </select>
      <span v-if="agentsLoading" class="muted hint">列表载入中…</span>
      <button v-else-if="agentsError" class="link-like" type="button" @click="retryAgents">agent 列表重试</button>

      <span class="win-group">
        <button
          v-for="w in WINDOWS" :key="w.v" type="button"
          class="win" :class="{ on: filter.window === w.v }" @click="pickWindow(w.v)"
        >{{ w.label }}</button>
      </span>
      <button class="btn ghost-inline" type="button" :disabled="loading" @click="$emit('refresh')">
        {{ loading ? '刷新中…' : '刷新' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.bar {
  margin-bottom: 12px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.lab {
  font-size: 13px;
}

.sel {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  background: #fff;
}

.hint {
  font-size: 12px;
}

.link-like {
  border: none;
  background: none;
  padding: 0;
  color: var(--brand);
  font-size: 12px;
}

.win-group {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
}

.win {
  border: none;
  background: #fff;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--muted);
}

.win.on {
  background: var(--brand);
  color: #fff;
}

.ghost-inline {
  padding: 5px 12px;
  font-size: 13px;
  background: #fff;
  color: var(--brand);
  border: 1px solid var(--border);
  border-radius: 4px;
}
</style>
