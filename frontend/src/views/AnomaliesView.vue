<script setup lang="ts">
// 异常页（一级菜单"异常"）：只拉 metrics/anomalies 单端点（实时事件列表，request 红显）。
// 行点击下钻原 trace（复用 trace-detail，不重复实现组件）。
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { metricsAnomalies } from '../api/metrics'
import type { MetricsAnomalies } from '../api/types'
import AnomaliesSection from '../components/AnomaliesSection.vue'
import MetricFilterBar from '../components/MetricFilterBar.vue'
import { useMetricFilter } from '../composables/useMetricFilter'

const router = useRouter()
const { filter } = useMetricFilter()

const payload = ref<MetricsAnomalies | null>(null)
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
    const res = await metricsAnomalies(a, w)
    if (my !== seq) return
    payload.value = res
  } catch (e) {
    if (my !== seq) return
    if (e instanceof ApiError) {
      errorMsg.value = `异常查询失败（${e.code}）：${e.message}`
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

    <!-- v1.14：size≤100 截断提示（total 来自后端 track_total_hits 真实计数） -->
    <p v-if="payload && payload.truncated" class="muted trunc-hint">
      窗口内共 {{ payload.total }} 条，仅显示最新 {{ payload.items.length }} 条
    </p>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading && !payload" class="muted">加载中…</p>

    <!-- payload 就绪才渲染 section：其内部自带"窗口内无异常（错误 = 0）"空文案，
         加载失败无旧数据时不显示该文案以免误导 -->
    <AnomaliesSection
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
