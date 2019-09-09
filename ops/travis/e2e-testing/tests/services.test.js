const auto = require('../utils/auto');
const utils = require('../utils/utils');

const {
  user,
  pass
} = utils.getRandUserAndPass();

beforeEach(async () => {
  // utils.addPageListeners(page);
  await page.goto(url);
}, goToTimeout);

test.skip('Get services', async () => {
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  const servicesUrl = url + "services";
  const {
    data
  } = await utils.waitForResponse(page, servicesUrl);
  console.log(data);

  await auto.logOut(page);
}, 30000);
