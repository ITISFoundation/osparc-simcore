const url = "http://localhost:9081/"

test('check site title', async () => {
  // page is already defined by the jest-puppeteer preset
  await page.goto(url);

  const title = await page.title();
  expect(title).toBe('oSPARC');
}, 10000);
