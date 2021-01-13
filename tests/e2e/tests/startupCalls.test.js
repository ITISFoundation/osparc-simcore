const auto = require('../utils/auto');
const utils = require('../utils/utils');

describe('Calls after logging in', () => {
  const {
    user,
    pass
  } = utils.getUserAndPass();

  beforeAll(async () => {
    await page.goto(url);
    await auto.register(page, user, pass);
    await page.waitFor(1000);
  }, ourTimeout);
  
  afterAll(async () => {
    await auto.logOut(page);
  }, ourTimeout);
  
  test('Profile', async () => {
    const responseEnv = await utils.fetchReq('me');
    expect(responseEnv.data["login"]).toBe(user);
  }, ourTimeout);

  test('Studies', async () => {
    const responseEnv = await utils.fetchReq('projects?type=user');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Templates', async () => {
    const responseEnv = await utils.fetchReq('projects?type=template');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Services', async () => {
    const responseEnv = await utils.fetchReq('catalog/services');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
    expect(responseEnv.data.length).toBeGreaterThan(0);
  }, ourTimeout);

  test('Locations', async () => {
    const responseEnv = await utils.fetchReq('storage/locations');
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
    expect(responseEnv.data.length).toBeGreaterThan(0);
  }, ourTimeout);
});
