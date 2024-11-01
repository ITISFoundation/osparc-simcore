/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const userMenuButtons = {
  "osparc": {
    "userMenuMyAccountBtn": true,
    "userMenuBillingCenterBtn": false,
    "userMenuPreferencesBtn": true,
    "userMenuOrganizationsBtn": true,
    "userMenuThemeSwitcherBtn": true,
    "userMenuAboutBtn": true,
    "userMenuAboutProductBtn": true,
    "userMenuLicenseBtn": true,
    "userMenuAccessTIPBtn": false,
    "userMenuLogoutBtn": true,
  },
  "s4l": {
    "userMenuMyAccountBtn": true,
    "userMenuBillingCenterBtn": true,
    "userMenuPreferencesBtn": true,
    "userMenuOrganizationsBtn": true,
    "userMenuThemeSwitcherBtn": true,
    "userMenuAboutBtn": true,
    "userMenuAboutProductBtn": true,
    "userMenuLicenseBtn": true,
    "userMenuAccessTIPBtn": false,
    "userMenuLogoutBtn": true,
  },
  "s4lacad": {
    "userMenuMyAccountBtn": true,
    "userMenuBillingCenterBtn": true,
    "userMenuPreferencesBtn": true,
    "userMenuOrganizationsBtn": true,
    "userMenuThemeSwitcherBtn": true,
    "userMenuAboutBtn": true,
    "userMenuAboutProductBtn": true,
    "userMenuLicenseBtn": true,
    "userMenuAccessTIPBtn": false,
    "userMenuLogoutBtn": true,
  },
  "s4llite": {
    "userMenuMyAccountBtn": true,
    "userMenuBillingCenterBtn": true,
    "userMenuPreferencesBtn": true,
    "userMenuOrganizationsBtn": true,
    "userMenuThemeSwitcherBtn": true,
    "userMenuAboutBtn": true,
    "userMenuAboutProductBtn": true,
    "userMenuLicenseBtn": true,
    "userMenuAccessTIPBtn": false,
    "userMenuLogoutBtn": true,
  },
  "tis": {
    "userMenuMyAccountBtn": true,
    "userMenuBillingCenterBtn": true,
    "userMenuPreferencesBtn": true,
    "userMenuOrganizationsBtn": true,
    "userMenuThemeSwitcherBtn": true,
    "userMenuAboutBtn": true,
    "userMenuAboutProductBtn": true,
    "userMenuLicenseBtn": true,
    "userMenuAccessTIPBtn": false,
    "userMenuLogoutBtn": true,
  },
  "tiplite": {
    "userMenuMyAccountBtn": true,
    "userMenuBillingCenterBtn": true,
    "userMenuPreferencesBtn": true,
    "userMenuOrganizationsBtn": true,
    "userMenuThemeSwitcherBtn": true,
    "userMenuAboutBtn": true,
    "userMenuAboutProductBtn": true,
    "userMenuLicenseBtn": true,
    "userMenuAccessTIPBtn": true,
    "userMenuLogoutBtn": true,
  },
};

const dedicatedCentersPerRole = {
  "USER": {
    "PO Center": false,
    "Admin Center": false,
  },
  "TESTER": {
    "PO Center": false,
    "Admin Center": false,
  },
  "PRODUCT_OWNER": {
    "PO Center": true,
    "Admin Center": false,
  },
  "ADMIN": {
    "PO Center": true,
    "Admin Center": true,
  },
};

for (const product in products) {
  if (product in users) {
    const productUrl = products[product];
    const productUsers = users[product];
    for (const user of productUsers) {
      const role = user.role;

      test.describe.serial(`User Menu Buttons: ${product}`, () => {
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

        test(`User Menu buttons per ${product}`, async () => {
          expect(userMenuButtons[product]).toBeDefined();

          // open user menu
          await page.getByTestId("userMenuBtn").click();

          const buttons = userMenuButtons[product];
          for (const buttonId in buttons) {
            const menuButton = page.getByTestId(buttonId);
            const isVisible = buttons[buttonId];
            if (isVisible) {
              await expect(menuButton).toBeVisible();
            } else {
              await expect(menuButton).toHaveCount(0);
            }
          }

          // close user menu
          await page.getByTestId("userMenuBtn").click();
        });

        test(`Dedicated Centers per Role in User Menu ${role}`, async () => {
          expect(dedicatedCentersPerRole[role]).toBeDefined();

          // open user menu
          await page.getByTestId("userMenuBtn").click();

          const buttons = dedicatedCentersPerRole[role];
          for (const buttonText in buttons) {
            const expected = buttons[buttonText];
            const isVisible = await page.getByText(buttonText).isVisible();
            expect(isVisible).toEqual(expected);
          }

          // close user menu
          await page.getByTestId("userMenuBtn").click();
        });
      });
    }
  }
}
