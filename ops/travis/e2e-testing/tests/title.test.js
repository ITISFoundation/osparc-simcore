const utils = require('../e2e_utils/utils');
const url = "http://localhost:9081/"

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, goToTimeout);

test('Check site title', async () => {
  const title = await utils.getPageTitle(page);
  expect(title).toBe('oSPARC');
}, 20000);
