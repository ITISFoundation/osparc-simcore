const startBrowser = require('../utils/startPuppe');
const auto = require('../utils/auto');
const utils = require('../utils/utils');

const demo = true;
const url = "http://127.0.0.1:9081/";
const {
  user,
  pass
} = utils.getUserAndPass();

async function run () {
  const browser = await startBrowser.getBrowser(demo);
  const page = await browser.newPage();
  await page.goto(url);

  // LOGIN
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  // DASHBOARD navigation
  await auto.dashboardAbout(page);
  await auto.dashboardPreferences(page);
  await auto.dashboardServiceBrowser(page);
  await auto.dashboardStudyBrowser(page);

  // NEW STUDY from Scratch
  await auto.dashboardNewStudy(page);
  await page.waitFor(2000);
  await auto.toDashboard(page);

  // First study removal
  await auto.dashboardDeleteFirstStudy(page);

  // NEW STUDY from Template
  const templateName = "Sleepers";
  await auto.dashboardOpenFirstTemplate(page, templateName);
  const timeForFirstNodeToFinish = 40000;
  await auto.runStudy(page, timeForFirstNodeToFinish);
  await auto.toDashboard(page);

  // First study edition
  await auto.dashboardEditFristStudyThumbnail(page);
  await page.waitFor(2000);

  await auto.dashboardDataBrowser(page);
  await page.waitFor(2000);

  // LOGOUT
  if (demo) {
    await page.waitFor(2000);
  }
  await auto.logOut(page);

  await browser.close();
}


run()
  .catch((e) => {
    console.log('Puppeteer error: ' + e);
    process.exit(1);
  });
