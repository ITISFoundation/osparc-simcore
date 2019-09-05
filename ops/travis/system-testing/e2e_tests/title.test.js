const startBrowser = require('../e2e_utils/startBrowser');
const utils = require('../e2e_utils/utils');

let browser;
let page;
const demo = false;
const url = "http://localhost:9081/"

beforeAll(async () => {
  browser = await startBrowser.launch(demo);
});

afterAll(async () => {
  await browser.close();
});

beforeEach(async () => {
  page = await browser.newPage();
  await page.goto(url);
}, 30000);

afterEach(async () => {
  await page.close();
});

test('Check site title', async () => {
  const title = await utils.getPageTitle(page);
  expect(title).toBe('oSPARC');
}, 20000);
