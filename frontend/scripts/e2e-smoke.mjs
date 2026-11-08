import puppeteer from 'puppeteer-core'
import path from 'node:path'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://127.0.0.1:5173'
const OUT = 'D:/ECE-yolo-project/backend/logs'

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
})

const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 1000 })
const errors = []
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
page.on('console', (message) => {
  if (message.type() === 'error') errors.push(`console: ${message.text()}`)
})

async function clickButton(text) {
  const clicked = await page.evaluate((label) => {
    const button = [...document.querySelectorAll('button')].find((item) =>
      item.textContent?.includes(label),
    )
    if (button) {
      button.click()
      return true
    }
    return false
  }, text)
  if (!clicked) throw new Error(`button not found: ${text}`)
}

// 1) Detect page: upload + run detection
await page.goto(`${BASE}/detect`, { waitUntil: 'networkidle2' })
await page.waitForSelector('input[type=file]')
const input = await page.$('input[type=file]')
await input.uploadFile(path.resolve('D:/ECE-yolo-project/backend/logs/visdrone-sample.jpg'))
await page.waitForFunction(() => document.body.innerText.includes('visdrone-sample.jpg'))
await clickButton('开始检测')
await page.waitForFunction(() => document.body.innerText.includes('检测结果'), { timeout: 60000 })
await page.waitForFunction(() => document.body.innerText.includes('个目标'), { timeout: 60000 })
await page.screenshot({ path: `${OUT}/p7-detect-result.png` })
console.log('detect: ok')

// 2) Knowledge search
await page.goto(`${BASE}/knowledge`, { waitUntil: 'networkidle2' })
await page.waitForSelector('textarea')
await page.type('textarea', 'VisDrone 数据集包含哪些目标类别？')
await clickButton('检索片段')
await page.waitForSelector('.snippet', { timeout: 60000 })
await page.screenshot({ path: `${OUT}/p7-knowledge-result.png` })
console.log('knowledge: ok')

// 3) Agent history
await page.goto(`${BASE}/agent`, { waitUntil: 'networkidle2' })
await page.waitForSelector('.conversation-item')
await page.evaluate(() => document.querySelector('.conversation-item')?.click())
await page.waitForSelector('.markdown-body', { timeout: 30000 })
await page.screenshot({ path: `${OUT}/p7-agent-history.png` })
console.log('agent history: ok')

console.log('errors:', errors.length)
for (const error of errors) console.log(error)
await browser.close()
if (errors.length) process.exitCode = 1
