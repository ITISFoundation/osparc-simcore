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
    loginPageFixture = new LoginPage(page, productUrl);
    const role = await loginPageFixture.login(user.email, user.password);
    expect(role).toBe(user.role);
  });

  test.afterAll(async ({ browser }) => {
    await loginPageFixture.logout();
    await page.close();
    await browser.close();
  });

  test(`Context`, async () => {
    const contextTree = page.getByTestId("contextTree");
    await expect(contextTree).toBeVisible({
      timeout: 30000 // it will take some time to load the Study Browser
    });

    const workspacesAndFoldersTreeItems = page.getByTestId("workspacesAndFoldersTreeItem");
    const count = await workspacesAndFoldersTreeItems.count();
    // at least two: My Workspace and Shared Workspaces
    expect(count > 1).toBeTruthy();
  });

  test(`Tags`, async () => {
    const tagsFilter = page.getByTestId("study-tagsFilter");
    await expect(tagsFilter).toBeVisible({
      timeout: 30000 // it will take some time to load the Study Browser
    });

    const tagFilterItems = page.getByTestId("study-tagFilterItem");
    const count = await tagFilterItems.count();
    // at least two and less than 6 (max five are shown)
    expect(count > 1 && count < 6).toBeTruthy();
  });
});
