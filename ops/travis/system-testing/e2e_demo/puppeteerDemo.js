const startBrowser = require('../e2e_utils/startBrowser');
const auto = require('../e2e_utils/auto');

const demo = true;
const url = "http://localhost:9081/"
const randUser = Math.random().toString(36).substring(7);
const userEmail = 'puppeteer_'+randUser+'@itis.testing';
const pass = Math.random().toString(36).substring(7);

async function run () {
  const browser = await startBrowser.launch(demo);
  const page = await browser.newPage();
  await page.goto(url);

  page.on('response', response => {
    if (response.url().endsWith("register")) {
      const respStatus = response.status();
      expect(respStatus).toBe(200);
    }
  });
  await auto.register(page, userEmail, pass);

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

  await auto.dashboardAbout(page);
  await auto.dashboardPreferences(page);
  await auto.dashboardServiceBrowser(page);
  await auto.dashboardDataBrowser(page);
  await auto.dashboardStudyBrowser(page);
  // await auto.dashboardEditStudyThumbnail(page);
  // await auto.dashboardNewStudy(page);
  // await auto.dashboardOpenFirstTemplateAndRun(page, templateName);
  // await auto.dashboardDeleteFirstStudy(page);
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