const puppeteer = require('puppeteer');

const auto = require('./auto');

let browser;
let page;
const demo = true;
const url = "http://localhost:9081/"
const randUser = Math.random().toString(36).substring(7);
const userEmail = 'puppeteer_'+randUser+'@itis.testing';
const pass = Math.random().toString(36).substring(7);

beforeAll(async () => {
  const visibleOptions = {
    headless: false,
    defaultViewport: null, // Defaults to an 800x600 viewport. null disables the default viewport.
    slowMo: 60 // Slows down Puppeteer operations by the specified amount of milliseconds.
  }
  const options = demo ? visibleOptions : {};
  browser = await puppeteer.launch(options);
}, 30000);

afterAll(async () => {
  browser.close();
});

beforeEach(async () => {
  page = await browser.newPage();
  await page.goto(url);
}, 30000);

afterEach(async () => {
  if (demo) {
    await page.waitFor(1000);
  }
  await page.close();
});

test('Register', async () => {
  page.on('response', response => {
    if (response.url().endsWith("register")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
  });
  await auto.register(page, userEmail, pass);
}, 30000);

test('Log In and Log Out', async () => {
  page.on('response', response => {
    if (response.url().endsWith("services")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
    else if (response.url().endsWith("locations")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
  });
  await auto.logIn(page, userEmail, pass);
  await auto.logOut(page);
}, 30000);
