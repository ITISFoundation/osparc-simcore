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

test('Get my profile', async () => {
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  const responseEnv = await page.evaluate(async () => {
    const response = await fetch('http://localhost:9081/v0/me');
    return await response.json();
  });
  expect(responseEnv.data["login"]).toBe(user);

  await auto.logOut(page);
}, 30000);

test('Get my studies', async () => {
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  const responseEnv = await page.evaluate(async () => {
    const response = await fetch('http://localhost:9081/v0/projects?type=user');
    return await response.json();
  });
  expect(Array.isArray(responseEnv.data)).toBeTruthy();

  await auto.logOut(page);
}, 30000);

test('Get templates', async () => {
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  const responseEnv = await page.evaluate(async () => {
    const response = await fetch('http://localhost:9081/v0/projects?type=template');
    return await response.json();
  });
  expect(Array.isArray(responseEnv.data)).toBeTruthy();

  await auto.logOut(page);
}, 30000);

test('Get services', async () => {
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  const responseEnv = await page.evaluate(async () => {
    const response = await fetch('http://localhost:9081/v0/services');
    return await response.json();
  });
  expect(Array.isArray(responseEnv.data)).toBeTruthy();
  expect(responseEnv.data.length).toBeGreaterThan(0);

  await auto.logOut(page);
}, 30000);
