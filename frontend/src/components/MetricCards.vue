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
  // P1-19：叫「平均 QPS」而不是「QPS」——后端口径是 total/整窗秒数（metrics.py 的
  // _load_overview），是**整窗平均速率**；而同一页图表的序列走**桶实际覆盖窗宽**折算
  // （_overview_series，v1.14 缺陷修）。两者口径不同，标题不区分会被读成同一个数。
  { label: '平均 QPS', main: fmtQps(props.cards?.qps) },
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

// v1.15：两组卡合并进**同一个栅格**。此前是两行 flex（上行 4 张、下行 3 张），
// `flex: 1 1 120px` 各行独立分配宽度 ⇒ 两行的列宽与列边界对不齐，7 张卡排下来
// 像两张表硬叠在一起。合并后由同一套列轨道统管，无论几列都逐列对齐。
const all = (): CardCell[] => [...perf(), ...counts()]
</script>

<template>
  <div class="cards">
    <template v-if="props.loading && !props.cards">
      <div class="card">
        <span class="lab">加载中…</span><b class="muted">-</b>
      </div>
    </template>
    <template v-else>
      <div v-for="c in all()" :key="c.label" class="card" :class="c.cls">
        <span class="lab">{{ c.label }}</span>
        <b>{{ c.main }}</b>
        <span v-if="c.sub" class="sub">{{ c.sub }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 单一栅格：auto-fit 让列数随可用宽度自适应，但**始终只有一套列轨道** ⇒ 逐列对齐。
   7 张卡在 1240 内容域下排成一行；窄屏折成 6/5/…列时仍是同一套轨道。 */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  gap: var(--sp-3);
}

.card {
  /* grid 项默认 min-width:auto，六位数的读数会把所在列撑破并挤压其余列，显式归零。 */
  min-width: 0;
  /* 底色用 --bg（页面底色）而非白：卡片是白面板上的**凹陷槽**，靠明度差成形，
     比"白卡 + 边框"少一层线、多一层结构。 */
  background: var(--bg);
  border: 1px solid var(--border);
  /* P1-20：左边条提到基础样式，让**所有卡同构** —— 于是「色条颜色」才是状态
     （中性 / 红 / 橙），而不是「有的卡有色条、有的没有」。
     此前只有 .err/.to 额外加 border-left，同行三张里 2 张有 1 张无。 */
  border-left: 3px solid var(--border);
  border-radius: var(--radius-sm);
  /* 2026-09-20 由 9/12/10 放宽：原值下标签与读数几乎贴住卡片边，读数区显挤。 */
  padding: var(--sp-4) var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

/* P1-20：只改颜色，宽度由 .card 基础样式统一给（3px）—— 三态同构。 */
.card.err {
  border-left-color: var(--error);
}

.card.to {
  border-left-color: var(--timeout);
}

.card b {
  font-size: 23px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
  /* 显式再声明一次：body 的 tabular-nums 靠继承生效，本组件若被单独挂载（如单测）
     或将来被塞进不对的容器里就会丢。读数等宽是本页可读性的下限，不靠继承赌。 */
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
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
