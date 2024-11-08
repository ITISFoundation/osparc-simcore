/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const product = "osparc";
const productUrl = products[product];
const user = users[product][0];

test.describe.serial(`Left Filters:`, () => {
  let page = null;
  let loginPageFixture = null;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();

    const responsePromise = page.waitForResponse('**/services/-/latest**', {
      timeout: 30000
    });

    loginPageFixture = new LoginPage(page, productUrl);
    const role = await loginPageFixture.login(user.email, user.password);
    expect(role).toBe(user.role);

    await responsePromise;

    await page.getByTestId("servicesTabBtn").click();
  });

  test.afterAll(async ({ browser }) => {
    await loginPageFixture.logout();
    await page.close();
    await browser.close();
  });

  test(`Filters`, async () => {
    const sharedWithButtons = page.getByTestId("service-sharedWithFilterItem");
    await expect(sharedWithButtons.first()).toBeVisible({
      timeout: 30000 // it will take some time to load the Study Browser
    });

    const countSharedWithButtons = await sharedWithButtons.count();
    // All Services
    // My Services
    // Shared with Me
    // Shared with Everyone
    expect(countSharedWithButtons === 4).toBeTruthy();


    const serviceTypeButtons = page.getByTestId("service-serviceTypeFilterItem");
    await expect(serviceTypeButtons.first()).toBeVisible({
      timeout: 30000 // it will take some time to load the Study Browser
    });

    const countServiceTypeButtons = await serviceTypeButtons.count();
    // Computational
    // Interactive
    expect(countServiceTypeButtons === 2).toBeTruthy();
  });
});
