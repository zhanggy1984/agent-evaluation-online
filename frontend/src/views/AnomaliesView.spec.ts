// 异常页排序测试（批 14 · P1-6 只做 /anomalies 面）。
// 判别性所在：**旧实现根本不传 sort**（`metricsAnomalies(a, w)` 两参），
// 所以「点表头 → 第三参变成 'duration'」这条断言在旧码上必红；只断言
// 「点完还有数据」是验不出来的（旧码点完照样有数据）。
// 另盯一处**刻意的设计**：sort 变化**不清空 payload** —— 清空会让下方 `v-else-if="payload"`
// 卸载整块、视觉上闪一下（批 8 在 /interfaces 上实测过的坑），所以这里反向钉住它。
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AnomalyItem, MetricsAnomalies } from '../api/types'
import AnomaliesView from './AnomaliesView.vue'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

const apiMock = vi.hoisted(() => ({ metricsAnomalies: vi.fn() }))
vi.mock('../api/metrics', () => apiMock)

function payload(dur: number, truncated = false): MetricsAnomalies {
  const item = {
    ts: 1758000000000, agent: 'a-1', trace_id: 't-1', interface: 'POST /chat',
    node: 'request', status: 'error', error_type: 'db_error', error_msg: null,
    duration_ms: dur,
  } as AnomalyItem
  return { items: [item], total: truncated ? 500 : 1, truncated } as MetricsAnomalies
}

/** 挂载并等首屏 load 落地（onMounted 里 void load() → await metricsAnomalies） */
async function mountView(truncated = false) {
  apiMock.metricsAnomalies.mockResolvedValue(payload(800, truncated))
  const w = mount(AnomaliesView)
  await Promise.resolve()
  await Promise.resolve()
  return w
}

const head = (w: ReturnType<typeof mount>) => w.find('.panel .head').text()
/** 耗列表头（按文案定位，不按 index —— 列序变了这里要跟着发现） */
const durTh = (w: ReturnType<typeof mount>) =>
  w.findAll('th').find(t => t.text().includes('耗时'))

beforeEach(() => {
  push.mockClear()
  apiMock.metricsAnomalies.mockReset()
})

describe('P1-6 异常页按耗时排序', () => {
  it('初始不传 sort：第三参为 null，表头文案是「时间倒序」', async () => {
    const w = await mountView()
    expect(apiMock.metricsAnomalies).toHaveBeenCalledWith(null, '24h', null)
    expect(head(w)).toContain('时间倒序')
    expect(durTh(w)!.classes()).not.toContain('on')
  })

  it('点耗时表头 ⇒ 第三次调用带 duration，表头文案与高亮同步翻转', async () => {
    const w = await mountView()
    await durTh(w)!.trigger('click')
    await Promise.resolve()
    await Promise.resolve()
    expect(apiMock.metricsAnomalies).toHaveBeenLastCalledWith(null, '24h', 'duration')
    expect(head(w)).toContain('按耗时降序')
    expect(durTh(w)!.classes()).toContain('on')
  })

  it('再点一次 ⇒ 恢复默认并在表头文案上如实体现（标题不能撒谎）', async () => {
    const w = await mountView()
    await durTh(w)!.trigger('click')
    await Promise.resolve()
    await durTh(w)!.trigger('click')
    await Promise.resolve()
    await Promise.resolve()
    expect(apiMock.metricsAnomalies).toHaveBeenLastCalledWith(null, '24h', null)
    expect(head(w)).toContain('时间倒序')
  })

  it('排序切换不清空 payload：切完表格仍在，不出现整块卸载', async () => {
    const w = await mountView()
    expect(w.find('table').exists()).toBe(true)
    // 点下后**不 await 微任务**：若实现改成「先 payload=null 再 load」，
    // 此刻的同步渲染里表格已消失（这正是要钉的那个闪）
    await durTh(w)!.trigger('click')
    expect(w.find('table').exists()).toBe(true)
    expect(w.find('.panel').exists()).toBe(true)
  })

  it('截断提示措辞随排序变：duration 序说「最慢」，不是「最新」', async () => {
    // 排序发生在取 size 之前 ⇒ duration 序截断后留下的是最慢的 N 条，写「最新」就是撒谎
    const w = await mountView(true)
    const hint = () => w.find('.trunc-hint').text()
    expect(hint()).toContain('仅显示最新')
    await durTh(w)!.trigger('click')
    await Promise.resolve()
    await Promise.resolve()
    expect(hint()).toContain('仅显示最慢')
    expect(hint()).not.toContain('最新')
  })
})
