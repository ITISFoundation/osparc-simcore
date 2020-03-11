const auto = require('../utils/auto');
const utils = require('../utils/utils');

const {
  user,
  pass
} = utils.getUserAndPass();

beforeAll(async () => {
  await page.goto(url);
}, ourTimeout);

test('Register, Log In and Log Out', async () => {
  page.on('response', async response => {
    if (response.url().endsWith("/config")) {
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
    else if (response.url().endsWith("/register")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
  });
  await auto.register(page, user, pass);

  page.on('response', async response => {
    if (response.url().endsWith("/login")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
    else if (response.url().endsWith("/me")) {
      try {
        const respStatus = response.status();
        expect(respStatus).toBe(200);
      }
      catch (e) {
        console.log("Pptr error", e);
      }
    }
  });
  await auto.logIn(page, user, pass);
  await auto.logOut(page);
}, 30000);
