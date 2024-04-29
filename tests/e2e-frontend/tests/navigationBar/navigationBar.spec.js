/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';
import users from '../users.json';

const poweredByOsparcIcon = {
  "osparc": false,
  "s4l": true,
  "s4lacad": true,
  "s4llite": true,
  "tis": true
};

for (const product in products) {
  if (product in users) {
    const productUsers = users[product];
    test.describe(`Navigation Bar ${product}`, () => {
      for (const user of productUsers) {

        test.beforeAll('Log in', async ({ page }) => {
          await page.goto(products[product]);
          user.email
          user.password
          user.role
        });

        test(`Items`, async ({ page }) => {
          expect(poweredByOsparcIcon[product]).toBeDefined();

          const expected = poweredByOsparcIcon[product];
          const isVisible = await page.getByTestId("poweredByOsparc").isVisible();
          expect(isVisible).toEqual(expected);
        });
      }
    });
  }
}
