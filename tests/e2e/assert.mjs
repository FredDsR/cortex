// Direct Playwright-library e2e for the viz world-search feature.
// Assumes a fixture site is served at http://127.0.0.1:8799.
import { chromium } from '@playwright/test';
import { readdirSync, existsSync } from 'fs';
import { join } from 'path';

// Playwright's pinned revision may be undownloadable in this sandbox; reuse any
// already-cached full chromium build via executablePath.
function findChrome() {
  const base = join(process.env.HOME, '.cache', 'ms-playwright');
  let dirs = [];
  try { dirs = readdirSync(base); } catch { return undefined; }
  dirs = dirs.filter(d => d.startsWith('chromium-') && !d.includes('headless')).sort().reverse();
  for (const d of dirs) {
    for (const sub of ['chrome-linux/chrome', 'chrome-linux64/chrome']) {
      const p = join(base, d, sub);
      if (existsSync(p)) return p;
    }
  }
  return undefined;
}
const EXE = findChrome();

const BASE = 'http://127.0.0.1:8799';
const SEARCH = '#appbar-search';
const ROW = '#search-results .search-result';

let pass = 0, fail = 0;
function ok(name) { pass++; console.log('PASS: ' + name); }
function bad(name, e) { fail++; console.log('FAIL: ' + name + ' -- ' + (e && e.message ? e.message : e)); }

async function ready(page, url = '/') {
  await page.goto(BASE + url, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector(SEARCH + ':not([disabled])', { timeout: 15000 });
}

const browser = await chromium.launch({ executablePath: EXE, args: ['--no-sandbox'] });
const page = await browser.newPage();
page.setDefaultTimeout(15000);

async function run(name, fn) {
  try { await fn(page); ok(name); }
  catch (e) { bad(name, e); }
}

async function firstTitle(page) {
  await page.waitForSelector(ROW, { timeout: 5000 });
  return (await page.textContent(ROW + ':first-child .search-title')) || '';
}

function assert(cond, msg) { if (!cond) throw new Error(msg); }

await run('index loads + search enabled', async (page) => {
  await ready(page);
  assert(await page.isVisible(SEARCH), 'search input not visible');
});

await run('exact query surfaces matching doc', async (page) => {
  await ready(page);
  await page.fill(SEARCH, 'task-a');
  const t = await firstTitle(page);
  assert(/Task a/.test(t), 'top result was: ' + t);
});

await run('fuzzy/typo match (typd -> typed)', async (page) => {
  await ready(page);
  await page.fill(SEARCH, 'typd');
  const t = await firstTitle(page);
  assert(/Frontmatter Title Wins/.test(t), 'top result was: ' + t);
});

await run('first-paragraph body text searchable', async (page) => {
  await ready(page);
  await page.fill(SEARCH, 'Blocked');
  await page.waitForSelector(ROW, { timeout: 5000 });
  const titles = await page.$$eval(ROW + ' .search-title', els => els.map(e => e.textContent));
  assert(titles.some(t => /Task a/.test(t)), 'titles: ' + JSON.stringify(titles));
});

await run('keyboard ArrowDown + Enter opens a result', async (page) => {
  await ready(page);
  await page.fill(SEARCH, 'task');
  await page.waitForSelector(ROW, { timeout: 5000 });
  await page.press(SEARCH, 'ArrowDown');
  await page.press(SEARCH, 'Enter');
  await page.waitForSelector('#search-results', { state: 'hidden', timeout: 5000 });
  const body = (await page.textContent('#content')) || '';
  assert(body.trim().length > 0, 'content pane empty after Enter');
});

await run('Escape + outside-click close the dropdown', async (page) => {
  await ready(page);
  await page.fill(SEARCH, 'task');
  await page.waitForSelector(ROW, { timeout: 5000 });
  await page.press(SEARCH, 'Escape');
  await page.waitForSelector('#search-results', { state: 'hidden', timeout: 5000 });
  await page.fill(SEARCH, 'task');
  await page.waitForSelector(ROW + '', { timeout: 5000 });
  await page.mouse.click(8, 400);   // click somewhere outside the box
  await page.waitForSelector('#search-results', { state: 'hidden', timeout: 5000 });
});

await run('in-scope result loads content + highlights + pulses', async (page) => {
  await ready(page);                     // root: all docs in scope
  await page.fill(SEARCH, 'task-a');
  await page.waitForSelector(ROW, { timeout: 5000 });
  await page.click(ROW + ':first-child');
  await page.waitForFunction(
    () => (document.querySelector('#content') || {}).textContent &&
          document.querySelector('#content').textContent.includes('Task a'),
    null, { timeout: 8000 });
  const cls = await page.getAttribute('#tree .tree-node[data-id="demo-ws/alpha/task/task-a"]', 'class');
  assert(/current/.test(cls || ''), 'tree node not current: ' + cls);
  assert(/search-pulse/.test(cls || ''), 'tree node not pulsing: ' + cls);
});

await run('out-of-scope result navigates to home page + opens doc', async (page) => {
  await page.goto(BASE + '/workspaces/demo-ws/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector(SEARCH + ':not([disabled])', { timeout: 15000 });
  // task-ghosted (kb-ghosts-ws) has no edge to demo-ws, so it is NOT in the
  // demo-ws graph -> out of scope -> must navigate to its home page.
  await page.fill(SEARCH, 'ghosted');
  await page.waitForSelector(ROW, { timeout: 5000 });
  // openResult fires on mousedown; dispatch it + await the cross-page navigation
  // together (a full click() can error on the detached mouseup during nav).
  await Promise.all([
    page.waitForURL(/kb-ghosts-ws\/sessions\/solo\/index\.html#doc=/, { timeout: 10000 }),
    page.locator(ROW + ':first-child').dispatchEvent('mousedown'),
  ]);
  await page.waitForFunction(
    () => document.querySelector('#content') &&
          document.querySelector('#content').textContent.includes('Task ghosted'),
    null, { timeout: 8000 });
});

await browser.close();
console.log('\n=== e2e summary: ' + pass + ' passed, ' + fail + ' failed ===');
process.exit(fail ? 1 : 0);
