const startBrowser = require('../e2e_utils/startBrowser');
const auto = require('../e2e_utils/auto');

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

  page.on('console', consoleObj => console.log(consoleObj.text()));

  page.on('response', async response => {
    if (response.url().endsWith("register")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
  });
  await page.goto(url);
}, 30000);

afterEach(async () => {
  await page.close();
});

test('Register', async () => {
  page.on('response', async response => {
    if (response.url().endsWith("config")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
      const dataObj = await response.json();
      expect(dataObj.data["invitation_required"]).toBeFalsy();
    }
  });
  await auto.register(page, userEmail, pass);
}, 30000);

test('Log In and Log Out', async () => {
  await auto.logIn(page, userEmail, pass);
  await auto.logOut(page);
}, 30000);
