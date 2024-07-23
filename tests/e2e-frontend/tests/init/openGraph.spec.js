/* eslint-disable no-undef */

const { test, expect } = require('@playwright/test');

import products from '../products.json';
import appsMetadata from '../../../../services/static-webserver/client/scripts/apps_metadata.json';

for (const product in products) {
  test(`Open Graph attributes ${product}`, async ({ page }) => {
    const app = appsMetadata.applications.find(app => app.application === product);
    expect(app).toBeDefined();

    const title = app.replacements.replace_me_og_title;
    const description = app.replacements.replace_me_og_description;
    const image = app.replacements.replace_me_og_image;

    await page.goto(products[product]);

    const ogTitle = page.locator('meta[property="og:title"]');
    await expect(ogTitle).toHaveAttribute('content', title);

    const ogDescription = page.locator('meta[property="og:description"]');
    await expect(ogDescription).toHaveAttribute('content', description);

    const ogImage = page.locator('meta[property="og:image"]');
    await expect(ogImage).toHaveAttribute('content', image);
  });
}
