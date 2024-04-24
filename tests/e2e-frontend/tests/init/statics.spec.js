/* eslint-disable no-undef */
const { test, expect } = require('@playwright/test');

import products from '../products.json';

const expectedStatics = {
  "osparc": {
    "isPaymentEnabled": false
  },
  "s4l": {
    "isPaymentEnabled": true
  },
  "s4lacad": {
    "isPaymentEnabled": true
  },
  "s4llite": {
    "isPaymentEnabled": false
  },
  "tis": {
    "isPaymentEnabled": true
  },
};

for (const product in products) {
  test(`is payment enabled ${product}`, async ({ page }) => {
    expect(product in expectedStatics).toBeTruthy();

    const responsePromise = page.waitForResponse('**/static-frontend-data.json');
    await page.goto(products[product]);

    const response = await responsePromise;
    const statics = await response.json();

    for (const staticKey in expectedStatics[product]) {
      expect(expectedStatics[product][staticKey] === statics[staticKey]).toBeTruthy();
    }
  });
}
