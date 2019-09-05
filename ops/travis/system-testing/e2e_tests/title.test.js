const startBrowser = require('../e2e_utils/startBrowser');
const utils = require('../e2e_utils/utils');

let browser;
const demo = false;
const url = "http://localhost:9081/"

beforeAll(async () => {
  browser = await startBrowser.launch(demo);
});

afterAll(async () => {
  await browser.close();
});

test('Check site title', async () => {
  let page = await browser.newPage();
  await page.goto(url);

  const title = await utils.getPageTitle(page);
  expect(title).toBe('oSPARC');

  await page.close();
}, 20000);
