import puppeteer from 'puppeteer-core'

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
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

await page.goto('http://127.0.0.1:5173/agent', { waitUntil: 'networkidle2' })
await page.waitForSelector('textarea')
await page.type('textarea', '请用一句话介绍这个平台')
await page.evaluate(() => {
  const button = [...document.querySelectorAll('button')].find((item) =>
    item.textContent?.includes('发送'),
  )
  button?.click()
})
await page.waitForFunction(
  () => document.querySelectorAll('.message-row.assistant').length > 0,
  { timeout: 180000 },
)
await page.waitForFunction(
  () => document.querySelector('.message-row.assistant .markdown-body')?.innerText.length > 0,
  { timeout: 180000 },
)
await page.screenshot({ path: 'D:/ECE-yolo-project/backend/logs/p7-agent-chat.png' })
console.log('agent chat: ok')
console.log('errors:', errors.length)
for (const error of errors) console.log(error)
await browser.close()
if (errors.length) process.exitCode = 1
