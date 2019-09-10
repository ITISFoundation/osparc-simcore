const auto = require('../utils/auto');
const utils = require('../utils/utils');

const {
  user,
  pass
} = utils.getRandUserAndPass();

beforeEach(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, goToTimeout);

test('Get services', async () => {
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  const responseEnv = await page.evaluate(async () => {
    const response = await fetch('http://localhost:9081/v0/services');
    return await response.json();
  });
  console.log();
  expect(responseEnv.data.length).toBeGreaterThan(0);

  await auto.logOut(page);
}, 30000);
