<script setup lang="ts">
// 前端分页页脚（批 49 / 任务 #44）：/interfaces、/anomalies、/llm-failures 三页共用。
//
// 哑组件 —— 页码状态由调用方持有（接口页两个 tab 各持一份，故不能放这里）。
//
// ⚠️ 为什么显示「本页已取 N 条」而不是只写「第 x / y 页」：这三页的数据在到达前端前
// 已被后端**截断**（接口页 terms size=50、异常/LLM 失败页 size≤100，页面上方另有一行
// 「窗口内共 M 条，仅显示…」）。只写「1 / 5」会让读者把「5 页」读成「窗口内就这 100 条」，
// 即**把「翻不完」读成「量就这么大」**。加上分子可消歧义，成本一行字。
import { PAGE_SIZE } from '../paging'

defineProps<{
  total: number   // 已取到的行数（不是窗口内总数）
  page: number    // 当前页，1 起
  pages: number   // 总页数，至少 1
}>()

const emit = defineEmits<{ (e: 'change', page: number): void }>()
</script>

<template>
  <!-- 批 49（用户拍板）：**非空即显示**，只有一页时也渲染「1 / 1」。
       与 /traces 的做法相反（那边 ≤1 页不显示），这里刻意对齐用户的诉求：
       接口页两个 tab 都要看得见分页控件。⚠️ 别把这两处「统一」掉 ——
       LLM 级接口通常只有个位数条数，按 /traces 的规则它**永远显示不出分页**，
       用户据此报过「LLM 级没加分页」（那是看不见，不是没做）。 -->
  <div v-if="total > 0" class="foot">
    <span class="muted">本页已取 {{ total }} 条</span>
    <button
      class="btn-ghost" type="button" :disabled="page <= 1"
      @click="emit('change', page - 1)"
    >上一页</button>
    <span class="page-no">{{ page }} / {{ pages }}</span>
    <button
      class="btn-ghost" type="button" :disabled="page >= pages"
      @click="emit('change', page + 1)"
    >下一页</button>
  </div>
</template>

<style scoped>
.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
}

/* 页码居中、数字等宽：翻页时宽度不跳（与 /traces 同观感） */
.page-no {
  margin: 0 2px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
</style>
