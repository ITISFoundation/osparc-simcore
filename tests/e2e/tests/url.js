module.exports = {
  checkUrl: () => {
    describe('Check URL', () => {
      beforeAll(async () => {
        console.log("Start:", new Date().toUTCString());

        await page.goto(url);
      }, ourTimeout);

      afterAll(async () => {
        console.log("End:", new Date().toUTCString());
      }, ourTimeout);

      test('Check site url', async () => {
        const url2 = page.url();
        expect(url2).toBe(url);
      }, 20000);
    });
  }
}
