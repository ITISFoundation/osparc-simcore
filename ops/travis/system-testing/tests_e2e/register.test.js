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

test('Register and Log In', async () => {
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

  await logIn(page, userEmail, pass);
}, 30000);

async function register(page, user, pass) {
  await page.waitForSelector('#loginCreateAccountBtn');
  await page.click('#loginCreateAccountBtn');

  await page.waitForSelector('#registrationEmailFld');
  await page.type('#registrationEmailFld', user);
  await page.type('#registrationPass1Fld', pass);
  await page.type('#registrationPass2Fld', pass);
  await page.click('#registrationSubmitBtn');
}

async function logIn(page, user, pass) {
  await page.waitForSelector('#loginUserEmailFld');
  await page.type('#loginUserEmailFld', user);
  await page.type('#loginPasswordFld', pass);
  await page.click('#loginSubmitBtn');
}
