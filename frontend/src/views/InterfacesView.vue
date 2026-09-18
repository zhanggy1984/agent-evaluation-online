<script setup lang="ts">
// 接口页（一级菜单"接口"）：只拉 metrics/interfaces 单端点，双 tab 请求级/LLM 级接口明细。
// 行级分位/计数走实时整窗（rollup 丢行级精度，源见 §8.4）；空态 = no_traffic。
import { computed, onMounted, ref, watch } from 'vue'

import { ApiError } from '../api/client'
import { metricsInterfaces } from '../api/metrics'
import type { MetricsInterfaces } from '../api/types'
import EmptyState from '../components/EmptyState.vue'
import InterfacesSection from '../components/InterfacesSection.vue'
import MetricFilterBar from '../components/MetricFilterBar.vue'
import { useMetricFilter } from '../composables/useMetricFilter'

const { filter } = useMetricFilter()

// 空态动作（P1-16）：清除筛选 = 回到默认窗口 + 全站（与 useMetricFilter 的默认值一致）
function resetFilter(): void {
  filter.window = '24h'
  filter.agent = ''
}

const payload = ref<MetricsInterfaces | null>(null)
const loading = ref(false)
const errorMsg = ref('')
let seq = 0

const hasRows = computed(() =>
  !!payload.value && (payload.value.request.length > 0 || payload.value.llm.length > 0))

async function load(): Promise<void> {
  const my = ++seq
  loading.value = true
  errorMsg.value = ''
  const a = filter.agent || null
  const w = filter.window
  try {
    const itf = await metricsInterfaces(a, w)
    if (my !== seq) return
    payload.value = itf
  } catch (e) {
    if (my !== seq) return
    if (e instanceof ApiError) {
      errorMsg.value = `接口查询失败（${e.code}）：${e.message}`
    } else {
      throw e
    }
  } finally {
    if (my === seq) loading.value = false
  }
}

watch(
  () => [filter.agent, filter.window] as const,
  () => {
    payload.value = null
    void load()
  },
)
onMounted(() => void load())
</script>

<template>
  <div>
    <MetricFilterBar :loading="loading" @refresh="load" />

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading && !payload" class="muted">加载中…</p>

    <template v-else-if="payload">
      <!-- 请求级/LLM 级桶均空 = 该范围无流量 → no_traffic；有桶才出 section（双 tab 明细） -->
      <EmptyState v-if="!hasRows" kind="no_traffic">
        <template #actions>
          <button
            v-if="filter.window !== '7d'"
            class="btn"
            type="button"
            @click="filter.window = '7d'"
          >改为近 7 天</button>
          <button class="btn-ghost" type="button" @click="resetFilter">清除筛选</button>
        </template>
      </EmptyState>
      <InterfacesSection v-else :payload="payload" :loading="loading" />
    </template>
  </div>
</template>
