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

test.describe(`Navigation Bar`, () => {
  test.describe.configure({
    mode: "serial"
  });

  for (const product in products) {
    if (product in users) {
      const productUsers = users[product];
      test.describe(`Navigation Bar ${product}`, () => {
        for (const user of productUsers) {
          const role = user.role;
          let page = null;
          let loginPageFixture = null;

          test.beforeAll(async ({ browser }) => {
            page = await browser.newPage();

            loginPageFixture = new LoginPage(page, products[product]);
            await loginPageFixture.goto();
            await loginPageFixture.login(user.email, user.password);
          });

          test.afterAll(async () => {
            await loginPageFixture.logout();
          });

          test(`Options per Role ${role}`, async () => {
            expect(userMenuButtonsPerRole[role]).toBeDefined();

            // open user menu
            await page.getByTestId("userMenuBtn").click();

            const buttons = userMenuButtonsPerRole[role];
            for (const buttonText in buttons) {
              const expected = buttons[buttonText];
              const isVisible = await page.getByText(buttonText).isVisible();
              expect(isVisible).toEqual(expected);
            }
          });
        }
      });
    }
  }
});
