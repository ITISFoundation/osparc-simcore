/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const expectedElements = {
  "osparc": {
    "plusButton": {
      "id": "newStudyBtn",
    },
  },
  "s4l": {
    "plusButton": {
      "id": "startS4LButton",
    },
  },
  "s4lacad": {
    "plusButton": {
      "id": "startS4LButton",
    },
  },
  "s4llite": {
    "plusButton": {
      "id": "startS4LButton",
    },
  },
  "tis": {
    "plusButton": {
      "id": "newStudyBtn",
    },
  },
  "tiplite": {
    "plusButton": {
      "id": "newStudyBtn",
    },
  },
};

for (const product in products) {
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

        test(`Plus button`, async () => {
          expect(expectedElements[product]["plusButton"]).toBeDefined();

          const plusButtonId = expectedElements[product]["plusButton"]["id"];
          const plusButton = page.getByTestId(plusButtonId);
          await expect(plusButton).toBeVisible({
            timeout: 30000 // it will take some time to load the Study Browser
          });
        });
      });
    }
  }
}
