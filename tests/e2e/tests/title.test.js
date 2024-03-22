const appMetadata = require('../../../services/static-webserver/client/scripts/apps_metadata.json')

beforeAll(async () => {
  await page.goto(url);
}, ourTimeout);

test('Check site title', async () => {
  // osparc ([¨0]) is the product served by default
  const replacements = appMetadata["applications"][0]["replacements"];

  const title = await page.title();
  expect(title).toBe(replacements["replace_me_og_title"]);

  const desc = document.querySelectorAll("head > meta[name='description']")[0].content;
  expect(desc).toBe(replacements["replace_me_og_description"]);

  // Open Graph metadata
  const ogTitle = document.querySelectorAll("head > meta[property='og:title']")[0].content;
  expect(ogTitle).toBe(replacements["replace_me_og_title"]);

  const ogDescription = document.querySelectorAll("head > meta[property='og:description']")[0].content;
  expect(ogDescription).toBe(replacements["replace_me_og_description"]);

}, 20000);
