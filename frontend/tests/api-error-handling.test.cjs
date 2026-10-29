const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const apiSource = fs.readFileSync(
  path.join(__dirname, '..', 'app', 'lib', 'api.ts'),
  'utf8',
);
const compiledApi = ts.transpile(apiSource, {
  module: ts.ModuleKind.CommonJS,
  target: ts.ScriptTarget.ES2020,
});

function loadFetchWithAuth(fetchImpl) {
  const apiModule = { exports: {} };
  vm.runInNewContext(compiledApi, {
    exports: apiModule.exports,
    module: apiModule,
    process: { env: {} },
    fetch: fetchImpl,
    console: { log() {}, warn() {} },
  });
  return apiModule.exports.fetchWithAuth;
}

test('preserves backend details from transient API 500 responses', async () => {
  const fetchWithAuth = loadFetchWithAuth(async () => ({
    ok: false,
    status: 500,
    statusText: 'Internal Server Error',
    text: async () => JSON.stringify({ detail: 'Progress service temporarily unavailable' }),
  }));

  await assert.rejects(
    fetchWithAuth('/api/v1/scrape-jobs/job-1'),
    /API 500: Progress service temporarily unavailable/,
  );
});

test('propagates rejected network promises without success-shaped fallbacks', async () => {
  const networkError = new TypeError('Network connection lost');
  const fetchWithAuth = loadFetchWithAuth(async () => {
    throw networkError;
  });

  await assert.rejects(
    fetchWithAuth('/api/v1/scrape-jobs/job-1'),
    error => error === networkError,
  );
});
