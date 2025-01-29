/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const expectedElements = {
  "osparc": {
    "newButton": {
      "id": "newPlusBtn"
    },
    "plusButton": {
      "id": "emptyStudyBtn",
    },
  },
  "s4l": {
    "newButton": {
      "id": "newPlusBtn"
    },
    "plusButton": {
      "id": "startS4LButton",
    },
  },
  "s4lacad": {
    "newButton": {
      "id": "newPlusBtn"
    },
    "plusButton": {
      "id": "startS4LButton",
    },
  },
  "s4llite": {
    "newButton": {
      "id": "newPlusBtn"
    },
    "plusButton": {
      "id": "startS4LButton",
    },
  },
  "tis": {
    "newButton": {
      "id": "newPlansBtn"
    },
    "plusButton": {
      "id": "newTIPlanButton",
    },
  },
  "tiplite": {
    "newButton": {
      "id": "newPlansBtn"
    },
    "plusButton": {
      "id": "newTIPlanButton",
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

        test(`Plus button after New button`, async () => {
          expect(expectedElements[product]["plusButton"]).toBeDefined();

          if (expectedElements[product]["newPlusButton"]) {
            const newPlusButton = page.getByTestId("newPlusBtn");
            await newPlusButton.click();
          }

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
