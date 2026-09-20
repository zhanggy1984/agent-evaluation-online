// 批 49（任务 #44）：LLM 失败页分页。
//
// 判别性所在：**旧实现渲染全部 items**（无分页）⇒「25 条只渲染 20 行」在旧码上必红。
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LlmFailuresSection from './LlmFailuresSection.vue'
import type { LlmFailureItem } from '../api/types'

function items(n: number): LlmFailureItem[] {
  return Array.from({ length: n }, (_, i) => ({
    ts: 1758000000000 + i, agent: 'a-1', trace_id: `t-${i}`, interface: 'POST /chat',
    request_status: 'ok', llm_node_status: 'error', model: 'm-1',
    llm_error_type: 'timeout', llm_error_msg: null,
  })) as LlmFailureItem[]
}

function mountSec(n: number) {
  return mount(LlmFailuresSection, { props: { items: items(n), loading: false } })
}

const bodyRows = (w: ReturnType<typeof mount>) => w.findAll('tbody tr').length

describe('批 49 LLM 失败页分页（每页 20）', () => {
  it('25 条：首屏 20 行 + 「1 / 2」；翻页后 5 行', async () => {
    const w = mountSec(25)
    expect(bodyRows(w)).toBe(20)
    expect(w.find('.page-no').text()).toBe('1 / 2')
    await w.findAll('button').find(b => b.text().includes('下一页'))!.trigger('click')
    expect(bodyRows(w)).toBe(5)
  })

  // 批 49（用户拍板）：只有一页时**也**渲染页脚（含「1 / 1」），两个按钮都禁用 ——
  // 与 /traces 相反，是刻意的不一致（LLM 级接口常只有个位数条数，藏起来会被读成「没做」）。
  it('正好 20 条（只有一页）：仍渲染「1 / 1」，两个按钮都禁用', () => {
    const w = mountSec(20)
    expect(bodyRows(w)).toBe(20)
    expect(w.find('.page-no').text()).toBe('1 / 1')
    const btn = (t: string) => w.findAll('button').find(b => b.text().includes(t))!
    expect(btn('上一页').attributes('disabled')).toBeDefined()
    expect(btn('下一页').attributes('disabled')).toBeDefined()
  })

  it('items 换代（刷新）⇒ 页码回到第 1 页', async () => {
    const w = mountSec(25)
    await w.findAll('button').find(b => b.text().includes('下一页'))!.trigger('click')
    expect(bodyRows(w)).toBe(5)
    await w.setProps({ items: items(25) })
    expect(bodyRows(w)).toBe(20)
    expect(w.find('.page-no').text()).toBe('1 / 2')
  })
})
