/**
 * HTML → PDF 渲染器（playwright-core）
 *
 * 解决三个跨机器坑：
 *  1) playwright-core 版本与本地 chromium 缓存版本可能不一致，
 *     必须显式指定 executablePath，否则报 "Executable doesn't exist"
 *  2) Windows 下不能用 /tmp/... 拼 file:// URL，必须用 pathToFileURL
 *  3) playwright-core 装在哪不固定 → 多路径探测 + PW_CORE 环境变量
 *
 * 用法：
 *   node html2pdf.js <输入html> <输出pdf> [A4|A5]
 *
 * 环境变量：
 *   PW_CORE      playwright-core 安装目录（可选，跳过自动探测）
 *   PW_BROWSERS  chromium 缓存目录（默认按平台推断）
 */
const path = require('path');
const fs = require('fs');
const os = require('os');
const { pathToFileURL } = require('url');

// playwright-core 安装位置（按优先级探测）
const PW_PATHS = [
  process.env.PW_CORE,
  path.join(__dirname, '..', 'node_modules', 'playwright-core'),
  path.join(process.cwd(), 'node_modules', 'playwright-core'),
  process.env.APPDATA ? path.join(process.env.APPDATA, 'npm/node_modules/playwright-core') : null,
  '/usr/local/lib/node_modules/playwright-core',
  '/opt/homebrew/lib/node_modules/playwright-core',
].filter(Boolean);

// chromium 缓存目录（跨平台）
function defaultCache() {
  if (process.env.PW_BROWSERS) return process.env.PW_BROWSERS;
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright');
  }
  if (process.platform === 'win32') {
    return path.join(process.env.LOCALAPPDATA || os.homedir(), 'ms-playwright');
  }
  return path.join(os.homedir(), '.cache', 'ms-playwright');
}

function findPw() {
  for (const p of PW_PATHS) {
    try {
      if (fs.existsSync(p)) return p;
    } catch (e) { /* 无权限则跳过 */ }
  }
  try {
    return require.resolve('playwright-core');
  } catch (e) {
    throw new Error(
      '找不到 playwright-core。请任选一种方式安装：\n' +
      '  npm i playwright-core\n' +
      '  或设置环境变量 PW_CORE 指向已安装目录'
    );
  }
}

function findChromium() {
  const cache = defaultCache();
  let dirs = [];
  try {
    dirs = fs.readdirSync(cache)
      .filter(d => /^chromium(_headless_shell)?-\d+$/.test(d))
      .sort((a, b) => parseInt(b.split('-').pop()) - parseInt(a.split('-').pop()));
  } catch (e) {
    throw new Error(
      `读不到 chromium 缓存目录 ${cache}。\n` +
      '  请运行：npx playwright install chromium\n' +
      '  或设置 PW_BROWSERS 指向实际缓存目录'
    );
  }
  for (const d of dirs) {
    for (const rel of [
      'chrome-win64/chrome.exe',
      'chrome-win/chrome.exe',
      'chrome-linux/chrome',
      'chrome-mac/Chromium.app/Contents/MacOS/Chromium',
      'chrome-headless-shell-linux64/chrome-headless-shell',
    ]) {
      const full = path.join(cache, d, rel);
      if (fs.existsSync(full)) return full;
    }
  }
  throw new Error(
    `缓存目录 ${cache} 下没有可用的 chromium 二进制。\n` +
    '  请运行：npx playwright install chromium'
  );
}

async function main() {
  const [input, output, paper] = process.argv.slice(2);
  if (!input || !output) {
    console.log('用法: node html2pdf.js <输入html> <输出pdf> [A4|A5]');
    process.exit(2);
  }
  if (!fs.existsSync(input)) {
    console.error(`找不到输入文件: ${input}`);
    process.exit(2);
  }

  const { chromium } = require(findPw());
  const browser = await chromium.launch({
    headless: true,
    executablePath: findChromium(),
  });

  try {
    const page = await browser.newPage({
      viewport: { width: 1200, height: 1600 },
      deviceScaleFactor: 2,       // 2倍图，印刷清晰度
    });
    await page.goto(pathToFileURL(path.resolve(input)).href, {
      waitUntil: 'networkidle',
      timeout: 60000,
    });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(600);

    const size = paper === 'A5' ? 'A5' : 'A4';
    await page.pdf({
      path: output,
      format: size,
      printBackground: true,      // 必须开，否则背景色丢失
      displayHeaderFooter: false,
    });
    const kb = (fs.statSync(output).size / 1024).toFixed(1);
    console.log(`PDF 完成: ${output} (${kb} KB, ${size})`);
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error('PDF 生成失败:', err.message);
  process.exit(1);
});