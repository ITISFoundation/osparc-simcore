const auto = require('../utils/auto');
const utils = require('../utils/utils');

describe('Calls after logging in', () => {
  const {
    user,
    pass
  } = utils.getUserAndPass();

  const responses = {
    me: null,
    studies: null,
    templates: null,
    services: null,
    locations: null,
  };

  beforeAll(async () => {
    page.on('response', response => {
      const url = response.url();
      if (url.endsWith('/me')) {
        responses.me = response.json();
      } else if (url.includes('projects?type=user')) {
        responses.studies = response.json();
      } else if (url.includes('projects?type=template')) {
        responses.templates = response.json();
      } else if (url.includes('catalog/services/-/latest')) {
        responses.services = response.json();
      } else if (url.includes('storage/locations')) {
        responses.locations = response.json();
      }
    });

    await page.goto(url);

    console.log("Registering user");
    await auto.register(page, user, pass);
    console.log("Registered");

    await page.waitFor(5000);
  }, ourTimeout);

  afterAll(async () => {
    await auto.logOut(page);
  }, ourTimeout);

  test('Profile', async () => {
    const responseEnv = await responses.me;
    expect(responseEnv.data["login"]).toBe(user);
  }, ourTimeout);

  test('Studies', async () => {
    const responseEnv = await responses.studies;
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Templates', async () => {
    const responseEnv = await responses.templates;
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
  }, ourTimeout);

  test('Services', async () => {
    const responseEnv = await responses.services;
    expect(responseEnv.data._meta.total).toBeGreaterThan(0);
    expect(Array.isArray(responseEnv.data.data)).toBeTruthy();
    expect(responseEnv.data.data.length).toBeGreaterThan(0);
  }, ourTimeout);

  test('Locations', async () => {
    const responseEnv = await responses.locations;
    expect(Array.isArray(responseEnv.data)).toBeTruthy();
    expect(responseEnv.data.length).toBeGreaterThan(0);
  }, ourTimeout);
});
