const auto = require('../utils/auto');
const utils = require('../utils/utils');

const {
  user,
  pass
} = utils.getRandUserAndPass();

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);

  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);
}, ourTimeout);

afterAll(async () => {
  await auto.logOut(page);
}, ourTimeout);

describe('Calls after logging in', () => {
  test('Profile', async () => {
    const responseEnv = await page.evaluate(async () => {
      const response = await fetch('http://localhost:9081/v0/me');
      return await response.json();
    });
    expect(responseEnv.data["login"]).toBe(user);
  }, ourTimeout);

  test('Studies', async () => {
    const responseEnv = await page.evaluate(async () => {
      const response = await fetch('http://localhost:9081/v0/projects?type=user');
      return await response.json();
    });
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Templates', async () => {
    const responseEnv = await page.evaluate(async () => {
      const response = await fetch('http://localhost:9081/v0/projects?type=template');
      return await response.json();
    });
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Services', async () => {
    const responseEnv = await page.evaluate(async () => {
      const response = await fetch('http://localhost:9081/v0/services');
      return await response.json();
    });
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
    expect(responseEnv.data.length).toBeGreaterThan(0);
  }, ourTimeout);
});
