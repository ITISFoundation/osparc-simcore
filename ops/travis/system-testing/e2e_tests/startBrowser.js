const puppeteer = require('puppeteer');

async function launch(demo) {
  const visibleOptions = {
    headless: false,
    devTools: true,
    defaultViewport: null, // Defaults to an 800x600 viewport. null disables the default viewport.
    slowMo: 60 // Slows down Puppeteer operations by the specified amount of milliseconds.
  }
  const options = demo ? visibleOptions : {};
  const browser = await puppeteer.launch(options);
  return browser;
}

module.exports = {
  launch,
}
