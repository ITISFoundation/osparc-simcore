const puppeteer = require('puppeteer');

const LOGS_DIR = "../logs/";

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

function listenToEvents(page) {
  const pathLib = require('path');
  const fs = require('fs');

  const logsDir = pathLib.join(__dirname, LOGS_DIR);
  if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir);
  }

  const event = new Date();
  const time = event.toLocaleTimeString('de-CH');
  let logsFilename = time + "_" + "devTools.log";
  logsFilename = logsFilename.split(":").join("-")
  const logsFile = pathLib.join(logsDir, logsFilename);

  const log4js = require("log4js");
  log4js.configure({
    appenders: {
      devTools: {
        type: "file",
        filename: logsFile
      }
    },
    categories: {
      default: {
        appenders: ["devTools"],
        level: "trace"
      }
    }
  });

  const logger = log4js.getLogger("devTools");
  page.on('console', msg => {
    logger.trace(msg.text());
  });
  page.on('pageerror', error => {
    logger.fatal(error.message);
  });
  page.on('response', response => {
    logger.info(response.status(), response.url());
  });
  page.on('requestfailed', request => {
    logger.error(request.failure().errorText, request.url);
  });
}

async function getPage(browser) {
  const page = await browser.newPage();
  page.setCacheEnabled(false);
  await page.setViewport({
    width: 1920,
    height: 1080
  });
  listenToEvents(page);
  return page;
}

module.exports = {
  getBrowser,
  getPage
}
