/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';

const poweredByOsparcIcon = {
  "osparc": false,
  "s4l": true,
  "s4lacad": true,
  "s4llite": true,
  "tis": true
};

for (const product in products) {
  await page.goto(products[product]);

  test(`Invitation required ${product}`, async ({ page }) => {
    expect(poweredByOsparcIcon[product]).toBeDefined();

    const expected = poweredByOsparcIcon[product];

    const button = page.getByTestId("poweredByOsparc");
    await expect(button).toBeVisible();
  });
}
