const startBrowser = require('../e2e_utils/startBrowser');

let browser;
const demo = false;
const url = "http://localhost:9081/"

beforeAll(async () => {
  browser = await startBrowser.launch(demo);
});

afterAll(() => {
  if (browser) {
    browser.close();
  }
});

test.skip('Check site title', async () => {
  const page = await browser.newPage();
  await page.goto(url);

  const title = await page.title();
  expect(title).toBe('oSPARC');

  page.close();
}, 20000);
