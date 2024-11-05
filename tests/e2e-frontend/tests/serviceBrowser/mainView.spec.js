/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const servicesTabExposed = {
  "osparc": {
    "areServicesExposed": true,
  },
  "s4l": {
    "areServicesExposed": true,
  },
  "s4lacad": {
    "areServicesExposed": true,
  },
  "s4llite": {
    "areServicesExposed": false,
  },
  "tis": {
    "areServicesExposed": false,
  },
  "tiplite": {
    "areServicesExposed": false,
  },
}

for (const product in products) {
  expect(servicesTabExposed[product]).toBeDefined();
  if (!servicesTabExposed[product]["areServicesExposed"]) {
    continue;
  }

  if (product in users) {
    const productUrl = products[product];
    const productUsers = users[product];
    for (const user of productUsers) {
      // expected roles for users: "USER"
      const role = "USER";
      expect(user.role).toBe(role);

      test.describe.serial(`Main View: ${product}`, () => {
        let page = null;
        let loginPageFixture = null;

        test.beforeAll(async ({ browser }) => {
          page = await browser.newPage();
          loginPageFixture = new LoginPage(page, productUrl);
          const role = await loginPageFixture.login(user.email, user.password);
          expect(role).toBe(user.role);
        });

        test.afterAll(async ({ browser }) => {
          await loginPageFixture.logout();
          await page.close();
          await browser.close();
        });

        test(`Services list`, async () => {
          const servicesList = page.getByTestId("servicesList");
          const serviceItems = servicesList.locator(':scope > *');
          const count = await serviceItems.count();
          expect(count > 0);
        });
      });
    }
  }
}
