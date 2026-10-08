#!/usr/bin/env node
const crypto = require('node:crypto')
function sandboxName(repo, pr, revision) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo) || !/^[1-9][0-9]*$/.test(String(pr)) || !/^[a-f0-9]{40}$/.test(revision)) {
    throw new Error('Expected owner/repo, a positive PR number and the full lowercase 40-character head SHA')
  }
  return 'box-' + crypto.createHash('sha256').update(`${repo.toLowerCase()}#${pr}@${revision}`).digest('hex').slice(0, 20)
}
module.exports = { sandboxName }
if (require.main === module) {
  try { console.log(sandboxName(...process.argv.slice(2))) }
  catch (err) { console.error(err.message); process.exitCode = 1 }
}
