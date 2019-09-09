const auto = require('../utils/auto');
const utils = require('../utils/utils');

const randUser = Math.random().toString(36).substring(7);
const userEmail = 'puppeteer_'+randUser+'@itis.testing';
const pass = Math.random().toString(36).substring(7);

beforeAll(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, goToTimeout);

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
