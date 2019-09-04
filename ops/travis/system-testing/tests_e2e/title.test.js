const startBrowser = require('./startBrowser');

let browser;
const demo = false;
const url = "http://localhost:9081/"

beforeAll(async () => {
  browser = await startBrowser.launch(demo);
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
}, 20000);
