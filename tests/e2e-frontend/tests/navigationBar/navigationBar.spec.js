/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';
import users from '../users.json';

const userMenuButtonsPerRole = {
  "user": {
    "My Account": true,
    "PO Center": false,
    "Admin Center": false,
  },
  "tester": {
    "My Account": true,
    "PO Center": false,
    "Admin Center": false,
  },
  "po_owner": {
    "My Account": true,
    "PO Center": true,
    "Admin Center": false,
  },
  "admin": {
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

          await page.goto(products[product]);
          await page.getByTestId("loginUserEmailFld").fill(user.email);
          await page.getByTestId("loginPasswordFld").fill(user.password);

          const responsePromise = page.waitForResponse('**/me');
          await page.getByTestId("loginSubmitBtn").click();

          const response = await responsePromise;
          const statics = await response.json();
          expect(statics["data"]["role"]).toBe(user.role);
        });

        test(`Role Centers`, async ({ page }) => {
          expect(userMenuButtonsPerRole[user.role]).toBeDefined();

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
