import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const workspace = fileURLToPath(new URL('../../', import.meta.url))
const web = resolve(workspace, 'web')
const check = spawnSync(process.execPath, ['scripts/check.mjs'], { cwd: web, encoding: 'utf8' })
assert.equal(check.error, undefined)
assert.equal(check.status, 0, `${check.stdout}${check.stderr}`)
const verification = JSON.parse(check.stdout)

const scope = [
  'web/src', 'web/scripts', 'web/vite.config.js', 'web/index.html',
  'web/package.json', 'web/package-lock.json', 'web/Dockerfile', 'web/nginx.conf'
]
const whitespace = spawnSync('git', ['diff', '--check', '--', ...scope], { cwd: workspace, encoding: 'utf8' })
assert.equal(whitespace.error, undefined)
assert.equal(whitespace.status, 0, `Scoped diff check failed: ${whitespace.stdout}${whitespace.stderr}`)

console.log(JSON.stringify({ ...verification, scopedDiffCheck: 'passed', scope }, null, 2))
