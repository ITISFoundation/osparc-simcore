const puppeteer = require('puppeteer');

async function launch(demo) {
  let options = {};
  const visibleOptions = {
    headless: false,
    devTools: true,
    defaultViewport: null, // Defaults to an 800x600 viewport. null disables the default viewport.
    slowMo: 60 // Slows down Puppeteer operations by the specified amount of milliseconds.
  }
  const woSandbox = {
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  };
  if (demo) {
    Object.assign(options, visibleOptions);
  }
  Object.assign(options, woSandbox);
  const browser = await puppeteer.launch();
  return browser;
}

module.exports = {
  launch,
}
