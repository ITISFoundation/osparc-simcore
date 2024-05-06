/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

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
    const productUrl = products[product];
    const productUsers = users[product];
    for (const user of productUsers) {
      const role = user.role;

      test.describe.serial(`Navigation Bar: ${product}`, () => {
        let page = null;
        let loginPageFixture = null;

        test.beforeAll(async ({ browser }) => {
          page = await browser.newPage();

          loginPageFixture = new LoginPage(page, productUrl);
          await loginPageFixture.goto();

          await loginPageFixture.login(user.email, user.password);

          const response = await page.waitForResponse('**/me');
          const meData = await response.json();
          expect(meData["data"]["role"]).toBe(role);
        });

        test.afterAll(async ({ browser }) => {
          await loginPageFixture.logout();
          await page.close();
          await browser.close();
        });

        test(`Options per Role in User Menu ${role}`, async () => {
          expect(userMenuButtonsPerRole[role]).toBeDefined();

          // open user menu
          await page.getByTestId("userMenuBtn").click();

          const buttons = userMenuButtonsPerRole[role];
          for (const buttonText in buttons) {
            const expected = buttons[buttonText];
            const isVisible = await page.getByText(buttonText).isVisible();
            expect(isVisible).toEqual(expected);
          }

          // close user menu
          await page.getByTestId("userMenuBtn").click();
        });
      });
    }
  }
}
