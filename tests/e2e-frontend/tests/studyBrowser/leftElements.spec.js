/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const product = "osparc";
const productUrl = products[product];
const user = users[product][0];

test.describe.serial(`User Menu Windows: ${product}`, () => {
  let page = null;
  let loginPageFixture = null;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    loginPageFixture = new LoginPage(page, productUrl);
    const role = await loginPageFixture.login(user.email, user.password);
    expect(role).toBe(user.role);
  });

  test.afterAll(async ({ browser }) => {
    await loginPageFixture.logout();
    await page.close();
    await browser.close();
  });

  test(`Context items`, async () => {
    const contextTree = page.getByTestId("contextTree");
    await expect(contextTree).toBeVisible();
  });

  test(`Tags`, async () => {
    const contextTree = page.getByTestId("tagsFilter");
    await expect(contextTree).toBeVisible();
  });
});
