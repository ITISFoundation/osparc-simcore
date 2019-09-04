const puppeteer = require('puppeteer');

let browser;
const demo = false;
const url = "http://localhost:9081/"

beforeAll(async () => {
  const visibleOptions = {
    headless: false,
    defaultViewport: null, // Defaults to an 800x600 viewport. null disables the default viewport.
    slowMo: 60 // Slows down Puppeteer operations by the specified amount of milliseconds.
  }
  const options = demo ? visibleOptions : {};
  browser = await puppeteer.launch(options);
});

afterAll(() => {
  browser.close();
});

test('Register, Log In and Log Out', async () => {
  const randUser = Math.random().toString(36).substring(7);
  const userEmail = 'puppeteer_'+randUser+'@itis.testing';
  const pass = Math.random().toString(36).substring(7);
  const page = await browser.newPage();
  await page.goto(url);

  page.on('response', response => {
    if (response.url().endsWith("register")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
  });

  await page.waitFor(1000);
  await register(page, userEmail, pass);

  page.on('response', response => {
    if (response.url().endsWith("me")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
    else if (response.url().endsWith("services")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
    else if (response.url().endsWith("locations")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
  });

  await page.waitFor(1000);
  await logIn(page, userEmail, pass);

  await page.waitFor(1000);
  await logOut(page);

}, 60000);

async function register(page, user, pass) {
  await page.waitForSelector('#loginCreateAccountBtn');
  await page.click('#loginCreateAccountBtn');

  await page.waitForSelector('#registrationEmailFld');
  await page.type('#registrationEmailFld', user);
  await page.type('#registrationPass1Fld', pass);
  await page.type('#registrationPass2Fld', pass);
  await page.waitForSelector('#registrationSubmitBtn');
  await page.click('#registrationSubmitBtn');
}

async function logIn(page, user, pass) {
  await page.waitForSelector('#loginUserEmailFld');
  await page.type('#loginUserEmailFld', user);
  await page.waitForSelector('#loginPasswordFld');
  await page.type('#loginPasswordFld', pass);
  await page.waitForSelector('#loginSubmitBtn');
  await page.click('#loginSubmitBtn');
}

async function logOut(page) {
  await page.waitForSelector('#userMenuMainBtn');
  await page.click('#userMenuMainBtn');

  await page.waitForSelector('#userMenuLogoutBtn');
  await page.click('#userMenuLogoutBtn');
}
