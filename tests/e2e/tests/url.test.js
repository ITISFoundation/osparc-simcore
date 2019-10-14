beforeAll(async () => {
  await page.goto(url);
}, ourTimeout);

test('Check site url', async () => {
  const url2 = page.url();
  expect(url2).toBe(url);
}, 20000);
