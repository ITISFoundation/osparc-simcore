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
    const responseEnv = await utils.fetch('me');
    expect(responseEnv.data["login"]).toBe(user);
  }, ourTimeout);

  test('Studies', async () => {
    const responseEnv = await utils.fetch('projects?type=user');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Templates', async () => {
    const responseEnv = await utils.fetch('projects?type=template');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  // ToDo: No registry is available for travis
  test.skip('Services', async () => {
    const responseEnv = await utils.fetch('services');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
    expect(responseEnv.data.length).toBeGreaterThan(0);
  }, ourTimeout);

  test('Locations', async () => {
    const responseEnv = await utils.fetch('storage/locations');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
    expect(responseEnv.data.length).toBeGreaterThan(0);
  }, ourTimeout);
});
