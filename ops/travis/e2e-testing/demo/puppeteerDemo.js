const startBrowser = require('../utils/startBrowser');
const auto = require('../utils/auto');
const utils = require('../utils/utils');

const demo = true;
const url = "http://localhost:9081/";
const {
  user,
  pass
} = utils.getRandUserAndPass();

async function run () {
  const browser = await startBrowser.launch(demo);
  const page = await browser.newPage();
  await page.goto(url);

  // LOGIN
  await auto.register(page, user, pass);
  await auto.logIn(page, user, pass);

  // DASHBOARD
  await auto.dashboardAbout(page);
  await auto.dashboardPreferences(page);
  await auto.dashboardServiceBrowser(page);
  await auto.dashboardStudyBrowser(page);

  await auto.dashboardNewStudy(page);
  await page.waitFor(2000);

  // STUDY EDITOR
  await auto.toDashboard(page);

  // DASHBOARD
  const templateName = "Sleepers";
  await auto.dashboardOpenFirstTemplateAndRun(page, templateName);

  // STUDY EDITOR
  await auto.toDashboard(page);

  // DASHBOARD
  await auto.dashboardEditFristStudyThumbnail(page);
  await page.waitFor(2000);
  // await auto.dashboardDataBrowser(page);
  await auto.dashboardDeleteFirstStudy(page);
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