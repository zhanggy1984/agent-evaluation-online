<script setup lang="ts">
// LLM 失败页（一级菜单"LLM 失败"）：只拉 metrics/llm-failures 单端点
// （请求 ok + LLM 节点失败的兜底/降级现场，v1 不回流）。行点击下钻原 trace。
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { metricsLlmFailures } from '../api/metrics'
import type { MetricsLlmFailures } from '../api/types'
import LlmFailuresSection from '../components/LlmFailuresSection.vue'
import MetricFilterBar from '../components/MetricFilterBar.vue'
import { useMetricFilter } from '../composables/useMetricFilter'

const router = useRouter()
const { filter } = useMetricFilter()

const payload = ref<MetricsLlmFailures | null>(null)
const loading = ref(false)
const errorMsg = ref('')
let seq = 0

function openTrace(row: { agent: string; traceId: string }): void {
  void router.push({ name: 'trace-detail', params: { agent: row.agent, traceId: row.traceId } })
}

async function load(): Promise<void> {
  const my = ++seq
  loading.value = true
  errorMsg.value = ''
  const a = filter.agent || null
  const w = filter.window
  try {
    const res = await metricsLlmFailures(a, w)
    if (my !== seq) return
    payload.value = res
  } catch (e) {
    if (my !== seq) return
    if (e instanceof ApiError) {
      errorMsg.value = `LLM 失败查询失败（${e.code}）：${e.message}`
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

    <!-- v1.14：折叠列表 size≤100 截断提示（total = 后端 cardinality 去重失败 trace 数） -->
    <p v-if="payload && payload.truncated" class="muted trunc-hint">
      窗口内共 {{ payload.total }} 条失败现场，仅显示最新 {{ payload.items.length }} 条
    </p>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading && !payload" class="muted">加载中…</p>

    <!-- payload 就绪才渲染 section：其内部自带"窗口内无 LLM 失败现场"空文案 -->
    <LlmFailuresSection
      v-else-if="payload" :items="payload.items" :loading="loading" @open="openTrace"
    />
  </div>
</template>

<style scoped>
.trunc-hint {
  margin: -2px 0 8px;
  font-size: 12px;
}
</style>
