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

function createLogFile() {
  const pathLib = require('path');
  const fs = require('fs');

  const logsDir = pathLib.join(__dirname, LOGS_DIR);
  if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir);
  }

  const event = new Date();
  const time = event.toLocaleTimeString('de-CH');
  let logsFilename = time + "_" + "e2e_logs.log";
  logsFilename = logsFilename.split(":").join("-")
  const logsFile = pathLib.join(logsDir, logsFilename);
  return logsFile;
}

function listenToEvents(page) {
  const logsFile = createLogFile()

  const log4js = require("log4js");
  log4js.configure({
    appenders: {
      e2eLogs: {
        type: "file",
        filename: logsFile
      }
    },
    categories: {
      default: {
        appenders: ["e2eLogs"],
        level: "trace"
      }
    }
  });

  const e2eLogger = log4js.getLogger("e2eLogs");
  page.on('console', msg => {
    e2eLogger.trace(msg.text());
  });
  page.on('pageerror', error => {
    e2eLogger.fatal(error.message);
  });
  page.on('response', response => {
    e2eLogger.info(response.status(), response.url());
  });
  page.on('requestfailed', request => {
    e2eLogger.error(request.failure().errorText, request.url);
  });
}

async function getPage(browser) {
  const page = await browser.newPage();
  page.setCacheEnabled(false);
  // NOTE: activate to see what happens in puppeteer evaluate function
  // page.on('console', consoleObj => console.log(consoleObj.text()));
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
