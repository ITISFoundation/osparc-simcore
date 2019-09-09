const utils = require('../e2e_utils/utils');
const url = "http://localhost:9081/"

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, goToTimeout);

test('Check site url', async () => {
  const url2 = utils.getPageUrl(page);
  expect(url2).toBe(url);
}, 20000);
