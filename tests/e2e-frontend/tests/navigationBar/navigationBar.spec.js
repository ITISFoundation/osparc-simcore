/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import { LoginPage } from '../fixtures/loginPage';

import products from '../products.json';
import users from '../users.json';

const expectedElements = {
  "osparc": {
    "poweredByOsparc": false,
    "studies": {
      "visible": true,
      "label": "STUDIES",
    },
    "templates": {
      "visible": true,
      "label": "TEMPLATES",
    },
    "services": {
      "visible": true,
      "label": "SERVICES",
    },
    "data": {
      "visible": true,
      "label": "DATA",
    },
  },
  "s4l": {
    "poweredByOsparc": true,
    "studies": {
      "visible": true,
      "label": "PROJECTS",
    },
    "templates": {
      "visible": true,
      "label": "TUTORIALS",
    },
    "services": {
      "visible": true,
      "label": "SERVICES",
    },
    "data": {
      "visible": false,
    },
  },
  "s4lacad": {
    "poweredByOsparc": true,
    "studies": {
      "visible": true,
      "label": "PROJECTS",
    },
    "templates": {
      "visible": true,
      "label": "TUTORIALS",
    },
    "services": {
      "visible": true,
      "label": "SERVICES",
    },
    "data": {
      "visible": false,
    },
  },
  "s4llite": {
    "poweredByOsparc": true,
    "studies": {
      "visible": true,
      "label": "PROJECTS",
    },
    "templates": {
      "visible": true,
      "label": "TUTORIALS",
    },
    "services": {
      "visible": false,
    },
    "data": {
      "visible": false,
    },
  },
  "tis": {
    "poweredByOsparc": true,
    "studies": {
      "visible": true,
      "label": "STUDIES",
    },
    "templates": {
      "visible": false,
    },
    "services": {
      "visible": false,
    },
    "data": {
      "visible": false,
    },
  },
  "tiplite": {
    "poweredByOsparc": true,
    "studies": {
      "visible": true,
      "label": "STUDIES",
    },
    "templates": {
      "visible": false,
    },
    "services": {
      "visible": false,
    },
    "data": {
      "visible": false,
    },
  },
};

for (const product in products) {
  if (product in users) {
    const productUrl = products[product];
    const productUsers = users[product];
    for (const user of productUsers) {
      const role = user.role;

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
          expect(meData["data"]["role"]).toBe(role);
        });

        test.afterAll(async ({ browser }) => {
          await loginPageFixture.logout();
          await page.close();
          await browser.close();
        });

        test(`Options per Role in User Menu ${role}`, async () => {
          expect(userMenuButtonsPerRole[role]).toBeDefined();

          // open user menu
          await page.getByTestId("userMenuBtn").click();

          const buttons = userMenuButtonsPerRole[role];
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
