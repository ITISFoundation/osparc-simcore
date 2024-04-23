/* eslint-disable no-undef */
const { test, expect } = require('@playwright/test');

import products from '../products.json';

const isPaymentEnabled = {
  "osparc": false,
  "s4l": true,
  "s4lacad": true,
  "s4llite": false,
  "tis": false
};

for (const product in products) {
  test(`is payment enabled ${product}`, async ({ page }) => {
    expect(product in isPaymentEnabled).toBeTruthy();

    const responsePromise = page.waitForResponse('**/static-frontend-data.json');

    await page.goto(products[product]);

    const response = await responsePromise;
    const statics = await response.body();
    const statics2 = await statics.json();
    console.log("statics", statics2);
    expect(isPaymentEnabled[product] === statics["isPaymentEnabled"]).toBeTruthy();
  });
}
