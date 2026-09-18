<script setup lang="ts">
// 登录页：POST /auth/login（§8.1）。admin/viewer 均可入；登录后落 /dashboard（T-2.4 看板落点）。
import { onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { login } from '../api/auth'
// P0-5：锁定（423）时用服务端下发的剩余秒数显示倒计时并置灰按钮。
// **不本地推算**——锁定是 900s 滑动窗口，前端给不出「第一次失败是什么时候」，见 loginLock.ts。
import { formatCountdown, retryAfterSeconds } from '../loginLock'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')
// 锁定剩余秒数：>0 = 锁定期中。0 = 未锁定（含倒计时走完，也含本就没锁）。
const lockLeft = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function stopCountdown(): void {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
  lockLeft.value = 0
}

function startCountdown(sec: number): void {
  stopCountdown()
  lockLeft.value = sec
  timer = setInterval(() => {
    lockLeft.value -= 1
    if (lockLeft.value <= 0) stopCountdown()
  }, 1000)
}

// 离开页面即停：后台空转的 interval 会在已卸载的组件上继续改 ref
onUnmounted(stopCountdown)

async function submit(): Promise<void> {
  if (loading.value || lockLeft.value > 0) return
  if (!username.value.trim() || !password.value) {
    errorMsg.value = '请输入用户名与密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await login(username.value.trim(), password.value)
    stopCountdown()
    await router.push({ name: 'overview' })
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '登录失败'
    const left = retryAfterSeconds(e)
    if (left !== null) startCountdown(left)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="panel login-card" @submit.prevent="submit">
      <h1 class="title">obs 观测台</h1>
      <p class="muted sub">agent 调用链路的错误聚类与回归回流平台</p>
      <label class="row">
        <span class="muted">用户名</span>
        <input v-model="username" name="username" autocomplete="username" />
      </label>
      <label class="row">
        <span class="muted">密码</span>
        <input v-model="password" type="password" name="password" autocomplete="current-password" />
      </label>
      <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
      <p v-if="lockLeft > 0" class="lock-text">
        还需 <strong>{{ formatCountdown(lockLeft) }}</strong> 可重试。锁定为后端进程内的失败计数，
        <strong>重启 backend 容器可立即清零</strong>。
      </p>
      <button class="btn" type="submit" :disabled="loading || lockLeft > 0">
        {{ loading ? '登录中…' : (lockLeft > 0 ? `已锁定（${formatCountdown(lockLeft)}）` : '登录') }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-wrap {
  display: flex;
  justify-content: center;
  padding-top: 12vh;
}

.login-card {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.title {
  font-size: 20px;
  margin: 0;
}

.sub {
  margin: 0 0 6px;
}

.row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* P0-5：锁定提示用警示色，与 401 的普通红字错登提示区分开 */
.lock-text {
  margin: 0;
  color: var(--timeout);
  font-size: 13px;
  line-height: 1.5;
}
</style>
