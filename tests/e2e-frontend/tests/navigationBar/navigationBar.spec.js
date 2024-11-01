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
    "notifications": true,
    "help": true,
    "credits": false,
    "userMenu": true,
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
    "notifications": true,
    "help": true,
    "credits": true,
    "userMenu": true,
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
    "notifications": true,
    "help": true,
    "credits": true,
    "userMenu": true,
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
    "notifications": true,
    "help": true,
    "credits": false,
    "userMenu": true,
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
    "notifications": true,
    "help": true,
    "credits": true,
    "userMenu": true,
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
    "notifications": true,
    "help": true,
    "credits": true,
    "userMenu": true,
  },
};

for (const product in products) {
  if (product in users) {
    const productUrl = products[product];
    const productUsers = users[product];
    for (const user of productUsers) {
      // expected roles for users: "USER"
      const role = "USER";
      expect(user.role).toBe(role);

      test.describe.serial(`Navigation Bar: ${product}`, () => {
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

        test(`Check poweredByOsparc icon`, async () => {
          expect(expectedElements[product]["poweredByOsparc"]).toBeDefined();

          const isVisible = expectedElements[product]["poweredByOsparc"];
          const button = page.getByTestId("poweredByOsparc");
          if (isVisible) {
            await expect(button).toBeVisible();
          } else {
            await expect(button).toHaveCount(0);
          }
        });

        test(`Check Dashboard tabs`, async () => {
          expect(expectedElements[product]["studies"]).toBeDefined();
          expect(expectedElements[product]["templates"]).toBeDefined();
          expect(expectedElements[product]["services"]).toBeDefined();
          expect(expectedElements[product]["data"]).toBeDefined();

          const isStudiesVisible = expectedElements[product]["studies"]["visible"];
          const studiesLabel = expectedElements[product]["studies"]["label"];
          const isTemplatesVisible = expectedElements[product]["templates"]["visible"];
          const templatesLabel = expectedElements[product]["templates"]["label"];
          const isServicesVisible = expectedElements[product]["services"]["visible"];
          const servicesLabel = expectedElements[product]["services"]["label"];
          const isDataVisible = expectedElements[product]["data"]["visible"];
          const dataLabel = expectedElements[product]["data"]["label"];

          const checkButton = async (locator, isVisible, label) => {
            const tabBtn = page.getByTestId(locator);
            if (isVisible) {
              await expect(tabBtn).toBeVisible();
              await expect(tabBtn).toContainText(label);
            } else {
              await expect(tabBtn).toHaveCount(0);
            }
          };

          await checkButton("studiesTabBtn", isStudiesVisible, studiesLabel);
          await checkButton("templatesTabBtn", isTemplatesVisible, templatesLabel);
          await checkButton("servicesTabBtn", isServicesVisible, servicesLabel);
          await checkButton("dataTabBtn", isDataVisible, dataLabel);
        });

        test(`Check Notifications button`, async () => {
          expect(expectedElements[product]["notifications"]).toBeDefined();

          const isVisible = expectedElements[product]["notifications"];
          const button = page.getByTestId("notificationsButton");
          if (isVisible) {
            await expect(button).toBeVisible();
          } else {
            await expect(button).toHaveCount(0);
          }
        });

        test(`Check Help button`, async () => {
          expect(expectedElements[product]["help"]).toBeDefined();

          const isVisible = expectedElements[product]["help"];
          const button = page.getByTestId("helpNavigationBtn");
          if (isVisible) {
            await expect(button).toBeVisible();
          } else {
            await expect(button).toHaveCount(0);
          }
        });

        test(`Check Credits button`, async () => {
          expect(expectedElements[product]["credits"]).toBeDefined();

          const isVisible = expectedElements[product]["credits"];
          const button = page.getByTestId("creditsIndicatorButton");
          if (isVisible) {
            await expect(button).toBeVisible();
          } else {
            await expect(button).toHaveCount(0);
          }
        });

        test(`Check User Menu button`, async () => {
          expect(expectedElements[product]["userMenu"]).toBeDefined();

          const isVisible = expectedElements[product]["userMenu"];
          const button = page.getByTestId("userMenuBtn");
          if (isVisible) {
            await expect(button).toBeVisible();
          } else {
            await expect(button).toHaveCount(0);
          }
        });
      });
    }
  }
}
