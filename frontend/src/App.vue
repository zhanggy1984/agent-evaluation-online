<script setup lang="ts">
// 根布局：监听 auth 过期广播 → 回登录页（api/client.ts 终局 401 触发）
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import { AUTH_EXPIRED_EVENT } from './api/client'

const router = useRouter()

function onExpired(): void {
  router.push({ name: 'login' })
}

onMounted(() => window.addEventListener(AUTH_EXPIRED_EVENT, onExpired))
onUnmounted(() => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired))
</script>

<template>
  <router-view />
</template>
