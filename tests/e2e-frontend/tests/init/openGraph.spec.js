/* eslint-disable no-undef */

// @ts-check
const {
  test,
  expect
} = require('@playwright/test');

import appsMetadata from '../../../../services/static-webserver/client/scripts/apps_metadata.json';

const PRODUCT_URLS = {
  "osparc": "https://osparc-master.speag.com/",
  "s4l": "https://s4l-master.speag.com/",
  "s4lacad": "https://s4l-acad-master.speag.com/",
  "s4llite": "https://s4l-lite-master.speag.com/",
  "tis": "https://tip-master.speag.com/",
};

for (const product in PRODUCT_URLS) {
  test(`Open Graph properties ${product}`, async ({ page }) => {
    const app = appsMetadata.applications.find(app => app.application === product);
    expect(app).toBeTruthy();
    if (app) {
      const title = app.replacements.replace_me_og_title;
      const description = app.replacements.replace_me_og_description;
      const image = app.replacements.replace_me_og_image;

      await page.goto(PRODUCT_URLS[product]);

      const ogTitle = page.locator('meta[property="og:title"]');
      await expect(ogTitle).toHaveAttribute('content', title);

      const ogDescription = page.locator('meta[property="og:description"]');
      await expect(ogDescription).toHaveAttribute('content', description);

      const ogImage = page.locator('meta[property="og:image"]');
      await expect(ogImage).toHaveAttribute('content', image);
    }
  });
}
