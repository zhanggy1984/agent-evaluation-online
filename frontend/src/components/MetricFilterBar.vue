<script setup lang="ts">
// 指标页共享筛选条（Q3/Q4/Q5 决策）：
// - {agent, window} 读写 useMetricFilter 模块级单例 → 切页/刷新保持，任一指标页改动即联动。
// - agent 下拉数据源 = GET /metrics/agents（动态实测）；空 = 全站。
// - 手动"刷新"按钮触发当前页重拉（总览另有自动刷新，见 OverviewView）。
// - v1.14：幽灵 agent（localStorage 持久化值掉出活跃列表）+ top100 截断提示 + 前台可见性刷新。
import { computed, onBeforeUnmount, onMounted } from 'vue'

import { useAgents } from '../composables/useAgents'
import { useMetricFilter, WINDOWS } from '../composables/useMetricFilter'

// 会话中新上线 agent 的可见性刷新节流（仅切回前台时查一次，非轮询）
const AGENTS_FRESH_MS = 60_000

defineProps<{ loading: boolean }>()
defineEmits<{ (e: 'refresh'): void }>()

const { filter } = useMetricFilter()
const {
  agents, total, truncated,
  loading: agentsLoading, errorMsg: agentsError, load: loadAgents, lastLoadMs,
} = useAgents()

// 幽灵 = 持久化 agent 已掉出"近 7d 有流量"列表（下线/改名/数据老化）：
// 不处理则 <select> 显示空白但 filter 仍指向它 → 静默"全站口径但有过滤"。
const ghost = computed(
  () => filter.agent !== '' && agents.value.length > 0 && !agents.value.includes(filter.agent),
)

function pickAgent(v: string): void {
  filter.agent = v
}

function pickWindow(v: string): void {
  filter.window = v as typeof filter.window
}

function retryAgents(): void {
  void loadAgents(true)
}

function onVisibility(): void {
  if (!document.hidden && Date.now() - lastLoadMs() > AGENTS_FRESH_MS) {
    void loadAgents(true) // 回到前台且列表超 60s 陈旧 → 补一轮（新上线 agent 可见）
  }
}

onMounted(() => {
  void loadAgents()
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => document.removeEventListener('visibilitychange', onVisibility))
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
    <!-- v1.14 辅助提示：幽灵 agent 清除 / top100 截断，随数据就绪出现 -->
    <div v-if="ghost" class="hint-line warn-text">
      「{{ filter.agent }}」已不在近 7d 有流量 agent 列表（可能已下线/改名）——当前筛选实际无数据命中
      <button class="link-like" type="button" @click="pickAgent('')">清除为全站</button>
    </div>
    <div v-else-if="truncated && !agentsLoading" class="hint-line muted">
      近 7d 共 {{ total }} 个 agent，下拉仅显示最活跃 {{ agents.length }} 个
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

.hint-line {
  margin-top: 6px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.warn-text {
  color: var(--danger, #c0392b);
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
