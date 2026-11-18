import assert from 'node:assert/strict'
import { getStaffDestination } from '../src/utils/staffNavigation.js'

for (const destination of [
  '/workbench',
  '/knowledge?tab=search&doc=policy-2026&view=source&page=4',
  '/graph?entity=%E6%94%BF%E7%AD%96',
  '/dsl#saved-rules'
]) {
  assert.equal(getStaffDestination(destination), destination)
}

for (const destination of [
  undefined,
  null,
  ['/workbench', '/knowledge'],
  '//example.com/knowledge',
  'https://example.com/knowledge',
  'javascript:alert(1)',
  '/login?redirect=/login',
  '/agent',
  '/knowledge/../login',
  '/knowledge%2f..%2flogin',
  '/knowledge\\example.com',
  '/knowledge\n?doc=policy'
]) {
  assert.equal(getStaffDestination(destination), '/knowledge')
}
