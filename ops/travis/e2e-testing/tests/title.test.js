const utils = require('../utils/utils');

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, ourTimeout);

test('Check site title', async () => {
  const title = await utils.getPageTitle(page);
  expect(title).toBe('oSPARC');
}, 20000);
