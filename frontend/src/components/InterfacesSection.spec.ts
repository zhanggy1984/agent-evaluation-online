// 批 49（任务 #44）：接口页分页 —— 两个 tab **各持一份页码**。
//
// 判别性所在：**旧实现渲染全部 50 行**（无分页）⇒「25 条只渲染 20 行」在旧码上必红。
// 第二条钉的是设计选择本身：若两个 tab 共用一个 `page`，在请求级翻到第 2 页（只剩 5 行）
// 再切到 LLM 级，会落在 LLM 级的第 2 页上 —— 两次渲染都是「5 行」，读起来像
// 「LLM 级也只有 5 条」，而 tab 标签上的计数写着 25。这条断言在「共用一个 page」的实现上必红。
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InterfacesSection from './InterfacesSection.vue'
import type { MetricsInterfaces } from '../api/types'

function mkPayload(n: number): MetricsInterfaces {
  return {
    source: 'realtime',
    request: Array.from({ length: n }, (_, i) => ({
      interface: `POST /chat/${i}`, total: 10 + i, error: 0, timeout: 0, p50: 1, p95: 2, p99: 3,
    })),
    llm: Array.from({ length: n }, (_, i) => ({
      interface: `POST /llm/${i}`, total: 5, error: 0, llm_failure_rate: 0, models: [],
    })),
  } as unknown as MetricsInterfaces
}

async function mountSec(n: number) {
  const w = mount(InterfacesSection, {
    props: { payload: mkPayload(n), loading: false, sort: '' },
  })
  await Promise.resolve()
  return w
}

const bodyRows = (w: ReturnType<typeof mount>) => w.findAll('tbody tr').length
const btn = (w: ReturnType<typeof mount>, text: string) =>
  w.findAll('button').find(b => b.text().includes(text))!

describe('批 49 接口页分页（每页 20，两个 tab 各自独立）', () => {
  it('请求级 25 条：首屏只渲染 20 行 + 页脚「1 / 2」', async () => {
    const w = await mountSec(25)
    expect(bodyRows(w)).toBe(20)
    expect(w.find('.page-no').text()).toBe('1 / 2')
    await btn(w, '下一页').trigger('click')
    expect(bodyRows(w)).toBe(5)
  })

  it('请求级翻到第 2 页后切到 LLM 级：落在第 1 页（20 行），不跟着停在第 2 页', async () => {
    const w = await mountSec(25)
    await btn(w, '下一页').trigger('click')
    expect(bodyRows(w)).toBe(5)
    await w.findAll('.tabs button')[1].trigger('click') // 切到 LLM 级
    expect(w.find('.page-no').text()).toBe('1 / 2')
    expect(bodyRows(w)).toBe(20)
  })

  // ⚠️ 这条对应真机里用户报的那句「LLM 级也要有分页」：LLM 级在真实数据下常常只有
  // 个位数接口（实测 24h/7d 均为 7），按 /traces 的「≤1 页不渲染」规则会**永远看不见**
  // 分页控件 ⇒ 被读成「没做」。故这里反向钉住「只有一页也渲染」。
  it('LLM 级只有 7 条（只有一页）：该 tab 仍渲染「1 / 1」', async () => {
    const w = await mountSec(7)
    await w.findAll('.tabs button')[1].trigger('click')
    expect(w.findAll('tbody tr').length).toBe(7)
    expect(w.find('.page-no').text()).toBe('1 / 1')
  })

  // 数据身份变化（排序切换 / 刷新都会换 payload 而不卸载本组件）⇒ 回到第 1 页。
  // 不重置的话会停在只剩 5 行的第 2 页上，而 tab 标签仍写着 25 —— 像「数据少了一半」。
  it('payload 换代（排序/刷新）：页码回到第 1 页', async () => {
    const w = await mountSec(25)
    await btn(w, '下一页').trigger('click')
    expect(bodyRows(w)).toBe(5)
    await w.setProps({ payload: mkPayload(25), sort: 'error' })
    expect(bodyRows(w)).toBe(20)
    expect(w.find('.page-no').text()).toBe('1 / 2')
  })
})
