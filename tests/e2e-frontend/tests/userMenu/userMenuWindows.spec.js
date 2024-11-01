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

  test(`Organizations window`, async () => {
    // open user menu
    await page.getByTestId("userMenuBtn").click();
    // open Organization window
    await page.getByTestId("userMenuOrganizationsBtn").click();

    // make sure the window opens
    const organizationsWindow = page.getByTestId("organizationsWindow");
    await expect(organizationsWindow).toBeVisible();
    // check there is at least one organization listed
    const organizationListItems = page.getByTestId("organizationListItem");
    const count = await organizationListItems.count();
    expect(count > 0).toBeTruthy();

    // close window
    await page.getByTestId("organizationsWindowCloseBtn").click();
  });

  test(`License pop up`, async () => {
    // open user menu
    await page.getByTestId("userMenuBtn").click();

    // open license in new tab
    await page.getByTestId("userMenuLicenseBtn").click();
    const newTabPromise = page.waitForEvent("popup");
    const newTab = await newTabPromise;
    await newTab.waitForLoadState();

    // close tab
    await newTab.close();
  });
});
