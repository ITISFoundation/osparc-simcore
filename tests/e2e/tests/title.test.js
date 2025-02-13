const appMetadata = require('../../../services/static-webserver/client/scripts/apps_metadata.json')

beforeAll(async () => {
  await page.goto(url);
}, ourTimeout);

test('Check site title', async () => {
  const title = await page.title();
  expect(title).toContain("PARC");

  // oSPARC ([0]) is the product served by default
  const replacements = appMetadata["applications"][0]["replacements"];

  const description = await page.$$eval("head > meta[name='description']", descriptions => {
    return descriptions[0].content;
  });
  expect(description).toBe(replacements["replace_me_og_description"]);

  // Open Graph metadata
  const ogTitle = await page.$$eval("head > meta[property='og:title']", ogTitles => {
    return ogTitles[0].content;
  });
  expect(ogTitle).toBe(replacements["replace_me_og_title"]);

  const ogDescription = await page.$$eval("head > meta[property='og:description']", ogDescriptions => {
    return ogDescriptions[0].content;
  });
  expect(ogDescription).toBe(replacements["replace_me_og_description"]);

}, 20000);
