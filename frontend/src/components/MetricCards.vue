<script setup lang="ts">
// 概览卡（T-2.4）：口径与 detail §8.4 钉死一致——p50/95/99 = request 锚全量 duration_ms
// （含 error/timeout），失败率 = error/总，超时率 = timeout/总。
import { fmtInt, fmtMs, fmtPct, fmtQps } from '../format'
import type { MetricsCards } from '../api/types'

const props = defineProps<{ cards: MetricsCards | null; loading: boolean }>()

interface CardCell {
  label: string
  main: string
  sub?: string
  cls?: 'err' | 'to' | 'ok' | ''
}

const perf = (): CardCell[] => [
  { label: 'QPS', main: fmtQps(props.cards?.qps) },
  { label: 'P50', main: `${fmtMs(props.cards?.p50 ?? null)} ms` },
  { label: 'P95', main: `${fmtMs(props.cards?.p95 ?? null)} ms` },
  { label: 'P99', main: `${fmtMs(props.cards?.p99 ?? null)} ms` },
]

const counts = (): CardCell[] => [
  { label: '请求总数', main: fmtInt(props.cards?.total ?? null) },
  {
    label: '错误',
    main: fmtInt(props.cards?.error ?? null),
    sub: fmtPct(props.cards?.error_rate),
    cls: 'err',
  },
  {
    label: '超时',
    main: fmtInt(props.cards?.timeout ?? null),
    sub: fmtPct(props.cards?.timeout_rate),
    cls: 'to',
  },
]
</script>

<template>
  <div class="cards">
    <template v-if="props.loading && !props.cards">
      <div class="card">
        <span class="lab">加载中…</span><b class="muted">-</b>
      </div>
    </template>
    <template v-else>
      <div class="row">
        <div v-for="c in perf()" :key="c.label" class="card">
          <span class="lab">{{ c.label }}</span><b>{{ c.main }}</b>
        </div>
      </div>
      <div class="row">
        <div v-for="c in counts()" :key="c.label" class="card" :class="c.cls">
          <span class="lab">{{ c.label }}</span>
          <b>{{ c.main }}</b>
          <span v-if="c.sub" class="sub">{{ c.sub }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.card {
  flex: 1 1 120px;
  min-width: 120px;
  background: #fafbfc;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card.err {
  border-left: 3px solid var(--error);
}

.card.to {
  border-left: 3px solid var(--timeout);
}

.card b {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.2;
}

.card.err b,
.card.err .sub {
  color: var(--error);
}

.card.to b,
.card.to .sub {
  color: var(--timeout);
}

.lab {
  font-size: 12px;
  color: var(--muted);
}

.sub {
  font-size: 12px;
  color: var(--muted);
}
</style>
