// traceLabels.ts 单测（P0-1）：error_type 值域**非闭合**，故断言重心不是「映射表配全」
// （那不可穷举），而是两条不变量：① 未知值**原样透传**、绝不吞原值；② 无 error_msg 时
// 必须显式说明，不许只剩一行裸码。fixture 取 2026-09-18 线上真实样本。
import { describe, expect, it } from 'vitest'
import { errorDetail, errorTypeHint } from './traceLabels'

describe('errorTypeHint', () => {
  it('常见 HTTP 码给人话', () => {
    expect(errorTypeHint('HTTP_422')).toBe('参数未通过校验')
    expect(errorTypeHint('HTTP_401')).toContain('未认证')
    expect(errorTypeHint('HTTP_504')).toContain('网关超时')
  })

  it('表外 4xx/5xx 按类兜底，不因缺键而空白', () => {
    expect(errorTypeHint('HTTP_418')).toBe('请求被上游拒绝')
    expect(errorTypeHint('HTTP_599')).toBe('上游服务故障')
  })

  it('非 4xx/5xx 不给解释（不硬套）', () => {
    expect(errorTypeHint('HTTP_302')).toBe('')
  })

  it('llm_ 前缀一律「LLM 调用失败」', () => {
    expect(errorTypeHint('llm_connection')).toBe('LLM 调用失败')
    expect(errorTypeHint('llm_timeout')).toBe('LLM 调用失败')
  })

  it('非闭合值域的业务扩展值不硬套解释（留给原样透传）', () => {
    expect(errorTypeHint('validation_error')).toBe('')
    expect(errorTypeHint('auth_error')).toBe('')
  })
})

describe('errorDetail', () => {
  it('无 error_msg 时显式说明未上报，不留一行裸码', () => {
    // 线上真实：/traces/good-question/1a784dc96eed71e1512b765a0e714702
    const s = errorDetail({ status: 'error', error_type: 'HTTP_422', error_msg: null })
    expect(s).toBe('HTTP_422（参数未通过校验） · 未上报错误消息详情')
    expect(s).not.toBe('HTTP_422')
  })

  it('有 error_msg 时保留原值：<type>（<解释>）：<msg>', () => {
    // 线上真实：/traces/good-question/a1e8a8e980554db9a6a308636e13f9a3
    expect(errorDetail({
      status: 'error', error_type: 'llm_connection', error_msg: '[Errno 111] Connection refused',
    })).toBe('llm_connection（LLM 调用失败）：[Errno 111] Connection refused')
  })

  it('未知 error_type 原样透传，且不硬造括号', () => {
    const s = errorDetail({ status: 'error', error_type: 'validation_error', error_msg: 'x' })
    expect(s).toBe('validation_error：x')
    expect(s).not.toContain('（')
  })

  it('未知 error_type 且无 msg：原值 + 未上报说明', () => {
    expect(errorDetail({ status: 'error', error_type: 'auth_error', error_msg: null }))
      .toBe('auth_error · 未上报错误消息详情')
  })

  it('status=error 而无 error_type（契约上不该出现）也不崩', () => {
    expect(errorDetail({ status: 'error', error_type: null, error_msg: 'boom' })).toBe('boom')
    expect(errorDetail({ status: 'error', error_type: null, error_msg: null }))
      .toBe('执行失败，未上报错误消息')
  })

  it('timeout 分支：有 msg 拼 msg，无 msg 给超时说明', () => {
    expect(errorDetail({ status: 'timeout', error_msg: 'upstream slow' }))
      .toBe('调用超时：upstream slow')
    expect(errorDetail({ status: 'timeout', error_msg: null }))
      .toBe('调用超时（未在阈值内返回）')
  })
})
