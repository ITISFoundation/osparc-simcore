const puppeteer = require('puppeteer');

let browser;
let page;
const url = "http://localhost:9081/"

beforeAll(async () => {
  browser = await puppeteer.launch();
  page = await browser.newPage();
});

afterAll(() => {
  browser.close();
});

test('Check site title', async () => {
  await page.goto(url);

  const title = await page.title();
  expect(title).toBe('oSPARC');
}, 14000);
