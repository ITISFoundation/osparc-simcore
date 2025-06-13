const auto = require('../utils/auto');
const utils = require('../utils/utils');

module.exports = {
  startupCalls: () => {
    describe('Calls after logging in', () => {
      const {
        user,
        pass
      } = utils.getUserAndPass();

      const responses = {
        me: null,
        tags: null,
        tasks: null,
        uiConfig: null,
        studies: null,
        templates: null,
        services: null,
      };

      beforeAll(async () => {
        console.log("Start:", new Date().toUTCString());

        page.on('response', response => {
          const url = response.url();
          if (url.endsWith('/me')) {
            responses.me = response.json();
          } else if (url.endsWith('/tags')) {
            responses.tags = response.json();
          } else if (url.endsWith('/tasks')) {
            responses.tasks = response.json();
          } else if (url.endsWith('/ui')) {
            responses.uiConfig = response.json();
          } else if (url.includes('projects?type=user')) {
            responses.studies = response.json();
          } else if (url.includes('projects?type=template')) {
            responses.templates = response.json();
          } else if (url.includes('catalog/services/-/latest')) {
            responses.services = response.json();
          }
        }, 120000);

        await page.goto(url);

        console.log("Registering user");
        await auto.register(page, user, pass);
        console.log("Registered");

        await page.waitFor(60000);
      }, ourTimeout);

      afterAll(async () => {
        await auto.logOut(page);

        console.log("End:", new Date().toUTCString());
      }, ourTimeout);

      test('Profile', async () => {
        const responseEnv = await responses.me;
        expect(responseEnv.data["login"]).toBe(user);
      }, ourTimeout);

      test('Tags', async () => {
        const responseEnv = await responses.tags;
        expect(Array.isArray(responseEnv.data)).toBeTruthy();
      }, ourTimeout);

      /*
      test('Tasks', async () => {
        const responseEnv = await responses.tasks;
        expect(Array.isArray(responseEnv.data)).toBeTruthy();
      }, ourTimeout);
      */

      test('UI Config', async () => {
        const responseEnv = await responses.uiConfig;
        expect(responseEnv.data["productName"]).toBe("osparc");
        const uiConfig = responseEnv.data["ui"];
        const isObject = typeof uiConfig === 'object' && !Array.isArray(uiConfig) && uiConfig !== null;
        expect(isObject).toBeTruthy();
      }, ourTimeout);

      test('Studies', async () => {
        const responseEnv = await responses.studies;
        expect(Array.isArray(responseEnv.data)).toBeTruthy();
      }, ourTimeout);

      /*
      // templates are lazy loaded
      test('Templates', async () => {
        const responseEnv = await responses.templates;
        expect(Array.isArray(responseEnv.data)).toBeTruthy();
      }, ourTimeout);
      */

      test('Services', async () => {
        const responseEnv = await responses.services;
        expect(responseEnv.data._meta.total).toBeGreaterThan(0);
        expect(Array.isArray(responseEnv.data.data)).toBeTruthy();
        expect(responseEnv.data.data.length).toBeGreaterThan(0);
      }, ourTimeout);
    });
  }
}
