/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';

const expectedLogin = {
  "osparc": {
    "label": "Request Account",
    "afterClicking": "registrationSubmitBtn",
  },
  "s4l": {
    "label": "Request Account",
    "afterClicking": "registrationSubmitBtn",
  },
  "s4lacad": {
    "label": "Request Account",
    "afterClicking": "registrationSubmitBtn",
  },
  "s4llite": {
    "label": "Request Account",
    "afterClicking": "createAccountWindow",
  },
  "tis": {
    "label": "Request Account",
    "afterClicking": "registrationSubmitBtn",
  },
  "tiplite": {
    "label": "Request Account",
    "afterClicking": "registrationSubmitBtn",
  },
};

for (const product in products) {
  test(`Invitation required text in ${product}`, async ({ page }) => {
    expect(expectedLogin[product]["label"]).toBeDefined();

    const expectedLabel = expectedLogin[product]["label"];
    await page.goto(products[product]);

    const button = page.getByTestId("loginCreateAccountBtn");
    await expect(button).toBeVisible();
    await expect(button).toContainText(expectedLabel);
  });

  test(`Callback action on Create Account ${product}`, async ({ page }) => {
    expect(expectedLogin[product]["afterClicking"]).toBeDefined();

    await page.goto(products[product]);

    const button = page.getByTestId("loginCreateAccountBtn");
    button.click();

    const expectedWidget = page.getByTestId(expectedLogin[product]["afterClicking"]);
    await expect(expectedWidget).toBeVisible();
  });
}
