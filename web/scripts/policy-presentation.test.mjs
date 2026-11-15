import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getSubsidyResult, getPolicySources, getPolicyConditions, getSourceUrl } from '../src/utils/policyPresentation.js'

const appliance = (result = {}, status = 'QUALIFIED') => ({ engine_result: {
  status,
  calculation_details: { result: { price: 5000, rate: .2, raw_subsidy: 1000, final_subsidy: 1000, per_item_cap: 2000, ...result } }
} })

test('standard appliance result retains server amount and raw capped formula separately', () => {
  const result = getSubsidyResult(appliance({ price: 20000, raw_subsidy: 4000, final_subsidy: 2000 }))
  assert.equal(result.amount, 2000)
  assert.equal(result.rawAmount, 4000)
  assert.equal(result.cap, 2000)
})

test('zero is a real amount and missing cap is not zero', () => {
  const result = getSubsidyResult(appliance({ price: 0, raw_subsidy: 0, final_subsidy: 0, per_item_cap: null }))
  assert.equal(result.amount, 0)
  assert.equal(result.cap, null)
})

test('expired, invalid and generic numeric DSL outputs never become money cards', () => {
  assert.equal(getSubsidyResult(appliance({}, 'EXPIRED')), null)
  assert.equal(getSubsidyResult(appliance({}, 'INVALID_INPUT')), null)
  assert.equal(getSubsidyResult({ engine_result: { status: 'SUCCESS', final_result: '15.0' } }), null)
  assert.equal(getSubsidyResult(appliance({ status: 'NOT_QUALIFIED' })), null)
})

test('incomplete, invalid, string, and nonfinite numeric fields are rejected', () => {
  for (const price of [null, '', '5000', NaN, Infinity, -1]) assert.equal(getSubsidyResult(appliance({ price })), null)
  assert.equal(getSubsidyResult(appliance({ rate: 20 })), null)
  assert.equal(getSubsidyResult(null), null)
})

test('sources tolerate missing records and use real engine source as a fallback', () => {
  assert.deepEqual(getPolicySources({ sources: [null, 4, {}] }), [])
  assert.deepEqual(getPolicySources({ engine_result: { policy_source: { title: '家电补贴细则', doc_id: '2026-1' } } }), [{ title: '家电补贴细则', path: '', origin: '2026-1' }])
  const sources = getPolicySources({ sources: [{ title: '2025 年政策', chunk_idx: 6 }] })
  assert.deepEqual(Object.keys(sources[0]), ['title', 'path', 'origin'])
})

test('only HTTP(S) and known served local paths can open originals', () => {
  assert.equal(getSourceUrl('https://www.gov.cn/policy.pdf#page=4'), 'https://www.gov.cn/policy.pdf#page=4')
  assert.equal(getSourceUrl('/api/uploads/policy.pdf'), '/api/uploads/policy.pdf')
  assert.equal(getSourceUrl('/resources/policy.pdf'), '/resources/policy.pdf')
  for (const path of ['javascript:alert(1)', 'data:text/html,x', '//evil.example/a', 'C:/secret/policy.pdf', '/api/uploads/../secret', 'https://user:pass@gov.cn/a', '/resources\\secret']) assert.equal(getSourceUrl(path), '')
})

test('condition snapshots preserve zero/false and ignore nested unknown values', () => {
  assert.deepEqual(getPolicyConditions({ inputs: { price: 0, eligible: false, nested: { value: 2 } } }), [
    { name: 'price', label: '购买金额', value: '0 元' },
    { name: 'eligible', label: 'eligible', value: 'false' }
  ])
  assert.deepEqual(getPolicyConditions({}), [])
})
