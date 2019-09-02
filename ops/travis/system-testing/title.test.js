const puppeteer = require('puppeteer');

const url = "http://localhost:9081/"

test('check site title', async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.goto(url);

  const title = await page.title();
  expect(title).toBe('oSPARC');
  
  console.log('Puppeteer is happy');
  await browser.close();
}, 16000);
