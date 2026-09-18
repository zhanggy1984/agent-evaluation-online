<script setup lang="ts">
// 空态/提示（T-2.4）：kind 收白名单，本批落 no_traffic/no_rollup；
// no_agent / second_phase 二期（L3 质量 tab / 弃留墙）再启用，接口先钉形状。
const props = defineProps<{ kind: 'no_traffic' | 'no_rollup' | 'no_agent' | 'second_phase' }>()

const copy: Record<string, { title: string; desc: string }> = {
  no_traffic: {
    title: '该范围暂无观测流量',
    desc: '窗口内无 request/llm_call 事件；换一个时间窗或 agent 再试。',
  },
  no_rollup: {
    title: '7d 小时聚合数据不可用',
    desc: '聚合数据未生成或缺口超出时间窗，当前按实时数据计算（短时间窗数值一致，可回溯的历史深度不同）。',
  },
  no_agent: {
    title: '该 agent 尚无指标数据',
    desc: '选中的 agent 未产生观测流量，或归属节点尚未注册。',
  },
  second_phase: {
    title: '二期能力（未启用）',
    desc: 'L3 质量 / 弃留墙等在二期接入，本页不预留灰置入口。',
  },
}
</script>

<template>
  <div class="empty panel">
    <p class="title">{{ copy[props.kind].title }}</p>
    <p class="muted desc">{{ copy[props.kind].desc }}</p>
    <!-- 可选动作（P1-16）：调用方不传则渲染结果与本批前完全一致 -->
    <div v-if="$slots.actions" class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.empty {
  text-align: center;
  padding: 34px 16px;
}

.title {
  margin: 0 0 6px;
  font-weight: 600;
}

.desc {
  margin: 0;
  font-size: 13px;
}

/* 空态动作行：仅当调用方传了 actions slot 才出现 */
.actions {
  margin-top: 14px;
  display: flex;
  gap: 8px;
  justify-content: center;
}
</style>
