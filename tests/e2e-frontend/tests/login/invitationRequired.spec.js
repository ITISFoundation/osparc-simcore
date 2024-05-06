/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';

const expectedCreateAccountLabel = {
  "osparc": "Create Account",
  "s4l": "Request Account",
  "s4lacad": "Request Account",
  "s4llite": "Request Account",
  "tis": "Request Account"
};

const expectedActionOnCreateAccount = {
  "osparc": "registrationSubmitBtn",
  "s4l": "registrationSubmitBtn",
  "s4lacad": "registrationSubmitBtn",
  "s4llite": "createAccountWindow",
  "tis": "createAccountWindow"
};

for (const product in products) {
  test(`Invitation required text in ${product}`, async ({ page }) => {
    expect(expectedCreateAccountLabel[product]).toBeDefined();

    const expectedLabel = expectedCreateAccountLabel[product];
    await page.goto(products[product]);

    const button = page.getByTestId("loginCreateAccountBtn");
    await expect(button).toBeVisible();
    await expect(button).toContainText(expectedLabel);
  });

  test(`Callback action on Create Account ${product}`, async ({ page }) => {
    expect(expectedActionOnCreateAccount[product]).toBeDefined();

    await page.goto(products[product]);

    const button = page.getByTestId("loginCreateAccountBtn");
    button.click();

    const expectedWidget = page.getByTestId(expectedActionOnCreateAccount[product]);
    await expect(expectedWidget).toBeVisible();
  });
}
