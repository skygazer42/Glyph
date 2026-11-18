import assert from 'node:assert/strict'
import { shouldOpenEvidence } from '../src/utils/consultationEvidence.js'

const ready = { sourceCount: 1, conditionCount: 0, compact: false, loading: false, manualChoice: null }
assert.equal(shouldOpenEvidence(ready), true)
assert.equal(shouldOpenEvidence({ ...ready, sourceCount: 0 }), false)
assert.equal(shouldOpenEvidence({ ...ready, sourceCount: 0, conditionCount: 2 }), true)
assert.equal(shouldOpenEvidence({ ...ready, loading: true }), false)
assert.equal(shouldOpenEvidence({ ...ready, compact: true }), false)
assert.equal(shouldOpenEvidence({ ...ready, manualChoice: false }), false)
