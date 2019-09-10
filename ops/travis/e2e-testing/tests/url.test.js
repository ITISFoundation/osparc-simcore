const utils = require('../utils/utils');

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, ourTimeout);

test('Check site url', async () => {
  const url2 = utils.getPageUrl(page);
  expect(url2).toBe(url);
}, 20000);
