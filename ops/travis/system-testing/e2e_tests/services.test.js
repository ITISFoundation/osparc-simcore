const startBrowser = require('../e2e_utils/startBrowser');
const auto = require('../e2e_utils/auto');
const utils = require('../e2e_utils/utils');

let browser;
let page;
const demo = false;
const url = "http://localhost:9081/"

const randUser = Math.random().toString(36).substring(7);
const userEmail = 'puppeteer_'+randUser+'@itis.testing';
const pass = Math.random().toString(36).substring(7);

beforeAll(async () => {
  browser = await startBrowser.launch(demo);
});

afterAll(async () => {
  await browser.close();
});

beforeEach(async () => {
  page = await browser.newPage();

  // Emitted when a script within the page uses `console`
  page.on('console', consoleObj => console.log(consoleObj.text()));
  // Emitted when the page emits an error event (for example, the page crashes)
  page.on('error', error => console.error(`Error ${error}`));
  // Emitted when a script within the page has uncaught exception
  page.on('pageerror', error => console.error(`Page Error ${error}`));

  await page.goto(url);
}, 30000);

afterEach(async () => {
  await page.close();
});

test.skip('Get services', async () => {
  await auto.register(page, userEmail, pass);
  await auto.logIn(page, userEmail, pass);

  const servicesUrl = url + "services";
  const {
    data
  } = await utils.waitForResponse(page, servicesUrl);
  console.log(data);

  await auto.logOut(page);
}, 30000);
