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
// P1-6：'' = 时间倒序（默认）| 'duration' = 按耗时降序。
// 本页局部 ref，不进 useMetricFilter（避免顺带改别的页的默认值）—— 同 /interfaces。
const sort = ref('')
let seq = 0

function toggleSort(): void {
  sort.value = sort.value === 'duration' ? '' : 'duration'
}

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
    const res = await metricsAnomalies(a, w, sort.value || null)
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
// ⚠️ sort 单独一个 watch，且**刻意不清空 payload**：清空会让下方 `v-else-if="payload"`
// 卸载整块，视觉上「点一下排序页面整个闪一下」——批 8 在 /interfaces 上实测过这个坑。
watch(sort, () => void load())

onMounted(() => void load())
</script>

<template>
  <div>
    <MetricFilterBar :loading="loading" @refresh="load" />

    <!-- v1.14：size≤100 截断提示（total 来自后端 track_total_hits 真实计数）。
         批 14：措辞随 sort 变 —— 排序发生在取 size 之前，duration 序截断后留下的是
         「最慢的 N 条」而非「最新的 N 条」，写死「最新」就是撒谎。 -->
    <p v-if="payload && payload.truncated" class="muted trunc-hint">
      窗口内共 {{ payload.total }} 条，仅显示{{ sort === 'duration' ? '最慢' : '最新' }}
      {{ payload.items.length }} 条
    </p>

    <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
    <p v-if="loading && !payload" class="muted">加载中…</p>

    <!-- payload 就绪才渲染 section：其内部自带"窗口内无异常（错误 = 0）"空文案，
         加载失败无旧数据时不显示该文案以免误导 -->
    <AnomaliesSection
      v-else-if="payload" :items="payload.items" :loading="loading" :sort="sort"
      @open="openTrace" @toggle-sort="toggleSort"
    />
  </div>
</template>

<style scoped>
.trunc-hint {
  margin: -2px 0 8px;
  font-size: 12px;
}
</style>
