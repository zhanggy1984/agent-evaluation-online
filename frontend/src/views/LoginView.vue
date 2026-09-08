<script setup lang="ts">
// 登录页：POST /auth/login（§8.1）。admin/viewer 均可入；登录后落 /dashboard（T-2.4 看板落点）。
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { login } from '../api/auth'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function submit(): Promise<void> {
  if (loading.value) return
  if (!username.value.trim() || !password.value) {
    errorMsg.value = '请输入用户名与密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await login(username.value.trim(), password.value)
    await router.push({ name: 'dashboard' })
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="panel login-card" @submit.prevent="submit">
      <h1 class="title">obs 观测台</h1>
      <p class="muted sub">agent-evaluation-online · 链路查询</p>
      <label class="row">
        <span class="muted">用户名</span>
        <input v-model="username" name="username" autocomplete="username" />
      </label>
      <label class="row">
        <span class="muted">密码</span>
        <input v-model="password" type="password" name="password" autocomplete="current-password" />
      </label>
      <p v-if="errorMsg" class="error-text">{{ errorMsg }}</p>
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
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
</style>
