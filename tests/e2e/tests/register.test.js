const auto = require('../utils/auto');
const utils = require('../utils/utils');

const {
  user,
  pass
} = utils.getUserAndPass();

const firstHandler = async response => {
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
}

const secondHandler = response => {
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
  else if (response.url().endsWith("/logout")) {
    expect(response.status()).toBe(200);
  }
}

beforeAll(async () => {
  await page.goto(url);
}, ourTimeout);

afterAll(async () => {
  page.off('response', firstHandler);
  page.off('response', secondHandler);
})

test('Register and Log Out', async () => {
  page.on('response', firstHandler);
  await auto.register(page, user, pass);
  page.on('response', secondHandler);
  await auto.logOut(page);
  await page.waitFor(5000);
}, ourTimeout);
