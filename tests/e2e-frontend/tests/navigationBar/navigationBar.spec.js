/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import LoginPage from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const userMenuButtonsPerRole = {
  "USER": {
    "My Account": true,
    "PO Center": false,
    "Admin Center": false,
  },
  "TESTER": {
    "My Account": true,
    "PO Center": false,
    "Admin Center": false,
  },
  "PRODUCT_OWNER": {
    "My Account": true,
    "PO Center": true,
    "Admin Center": false,
  },
  "ADMIN": {
    "My Account": true,
    "PO Center": true,
    "Admin Center": true,
  },
};

for (const product in products) {
  if (product in users) {
    const productUsers = users[product];
    test.describe(`Navigation Bar ${product}`, () => {
      for (const user of productUsers) {

        test.beforeAll('Log in', async () => {
          const browser = await chromium.launch();
          const page = await browser.newPage();

          const loginPage = LoginPage(page, products[product]);
          await loginPage.goto();

          const responsePromise = page.waitForResponse('**/me');
          await loginPage.login(user.email, user.password);

          const response = await responsePromise;
          const statics = await response.json();
          expect(statics["data"]["role"]).toBe(user.role);
        });

        test(`Options per Role ${user.role}`, async ({ page }) => {
          expect(userMenuButtonsPerRole[user.role]).toBeDefined();

          // open user menu
          await page.getByTestId("userMenuBtn").click();

          const buttons = userMenuButtonsPerRole[user.role];
          for (const button in buttons) {
            const expected = buttons[button];
            const isVisible = await page.getByRole("button", {
              name: button
            }).isVisible();
            expect(isVisible).toEqual(expected);
          }
        });
      }
    });
  }
}
