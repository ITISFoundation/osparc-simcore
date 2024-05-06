/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';

const expectedStatics = {
  "osparc": {
    "displayName": "o²S²PARC",
    "isPaymentEnabled": false
  },
  "s4l": {
    "displayName": "Sim4Life",
    "isPaymentEnabled": true
  },
  "s4lacad": {
    "displayName": "Sim4Life Science",
    "isPaymentEnabled": true
  },
  "s4llite": {
    "displayName": "<i>S4L<sup>lite</sup></i>",
    "isPaymentEnabled": false
  },
  "tis": {
    "displayName": "TI Planning Tool",
    "isPaymentEnabled": true
  },
};

for (const product in products) {
  test(`statics response in ${product}`, async ({ page }) => {
    expect(expectedStatics[product]).toBeDefined();

    const responsePromise = page.waitForResponse('**/static-frontend-data.json');
    await page.goto(products[product]);

    const response = await responsePromise;
    const statics = await response.json();

    for (const staticKey in expectedStatics[product]) {
      expect(statics[staticKey]).toBe(expectedStatics[product][staticKey]);
    }
  });
}
