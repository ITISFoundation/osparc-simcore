/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const product = "s4l";
const productUrl = products[product];
const user = users[product];

test.describe.serial(`Navigation Bar: ${product}`, () => {
  let page = null;
  let loginPageFixture = null;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();

    loginPageFixture = new LoginPage(page, productUrl);
    await loginPageFixture.goto();

    await loginPageFixture.login(user.email, user.password);

    const response = await page.waitForResponse('**/me');
    const meData = await response.json();
    expect(meData["data"]["role"]).toBe(user.role);
  });

  test.afterAll(async ({ browser }) => {
    await loginPageFixture.logout();
    await page.close();
    await browser.close();
  });

  test(`Organizations window`, async () => {
    // open user menu
    await page.getByTestId("userMenuBtn").click();
    // open Organization
    await page.getByTestId("userMenuOrganizationsBtn").click();

    // make sure the window opens
    const organizationsWindow = page.getByTestId("organizationsWindow");
    await expect(organizationsWindow).toBeVisible();
    // check there is at least one organization listed
    const organizationListItems = page.getByTestId("organizationListItem");
    const count = await organizationListItems.count();
    expect(count).toBeTruthy();
  });
});
