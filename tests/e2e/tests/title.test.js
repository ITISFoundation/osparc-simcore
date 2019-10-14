beforeAll(async () => {
  await page.goto(url);
}, ourTimeout);

test('Check site title', async () => {
  const title = await page.title();
  expect(title).toBe('oSPARC');
}, 20000);
