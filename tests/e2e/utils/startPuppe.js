const puppeteer = require('puppeteer');

async function getBrowser(demo) {
  let options = {};
  if (demo) {
    const visibleOptions = {
      headless: false,
      devTools: true,
      defaultViewport: null, // Defaults to an 800x600 viewport. null disables the default viewport.
      slowMo: 80 // Slows down Puppeteer operations by the specified amount of milliseconds.
    };
    Object.assign(options, visibleOptions);
  }
  else {
    const woSandbox = {
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--start-maximized'
      ]
    };
    Object.assign(options, woSandbox);
  }
  const browser = await puppeteer.launch(options);
  return browser;
}

async function getPage(browser) {
  const page = await browser.newPage();
  page.setCacheEnabled(false);
  await page.setViewport({
    width: 1920,
    height: 1080
  });
  return page;
}

module.exports = {
  getBrowser,
  getPage
}
