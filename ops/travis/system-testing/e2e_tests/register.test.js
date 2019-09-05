const startBrowser = require('../e2e_utils/startBrowser');
const auto = require('../e2e_utils/auto');

let browser;
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

test('Register', async () => {
  const page = await browser.newPage();
  await page.goto(url);
  await auto.register(page, userEmail, pass);
}, 30000);

test.skip('Log In and Log Out', async () => {
  await auto.logIn(page, userEmail, pass);
  await auto.logOut(page);
}, 30000);
