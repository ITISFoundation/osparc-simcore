const puppeteer = require('puppeteer');

let browser;
const demo = false;
const url = "http://localhost:9081/"

beforeAll(async () => {
  const visibleOptions = {
    headless: false,
    defaultViewport: null, // Defaults to an 800x600 viewport. null disables the default viewport.
    slowMo: 60 // Slows down Puppeteer operations by the specified amount of milliseconds.
  }
  const options = demo ? visibleOptions : {};
  browser = await puppeteer.launch(options);
});

afterAll(() => {
  browser.close();
});

test('Check site title', async () => {
  const page = await browser.newPage();
  await page.goto(url);

  const title = await page.title();
  expect(title).toBe('oSPARC');

  page.close();
}, 14000);
