const startBrowser = require('../utils/startBrowser');
const auto = require('../utils/auto');
const utils = require('../utils/utils');

const url = "http://localhost:9081/"

const randUser = Math.random().toString(36).substring(7);
const userEmail = 'puppeteer_'+randUser+'@itis.testing';
const pass = Math.random().toString(36).substring(7);

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, goToTimeout);

test('Register, Log In and Log Out', async () => {
  page.on('response', async response => {
    if (response.url().endsWith("config")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
        const responseBody = await response.json();
        expect(responseBody.data["invitation_required"]).toBeFalsy();
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
    else if (response.url().endsWith("register")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
  });
  await auto.register(page, userEmail, pass);

  page.on('response', async response => {
    if (response.url().endsWith("login")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
    else if (response.url().endsWith("me")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
  });
  await auto.logIn(page, userEmail, pass);
  await auto.logOut(page);
}, 30000);
