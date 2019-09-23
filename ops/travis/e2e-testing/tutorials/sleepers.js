const startBrowser = require('../utils/startBrowser');
const auto = require('../utils/auto');
// const utils = require('../utils/utils');

const demo = true;
/*
const {
  user,
  pass
} = utils.getRandUserAndPass();
*/
const user = "maiz@itis.swiss";
const pass = "osparc";

async function runTutorial (url) {
  console.log("Running tutorial on", url);
  const browser = await startBrowser.launch(demo);
  const page = await browser.newPage();
  await page.goto(url);

  // await auto.register(page, user, pass);
  // Login
  await auto.logIn(page, user, pass);

  // Use template to create Sleepers study
  // Run pipeline
  const templateName = "Sleepers";
  await auto.dashboardOpenFirstTemplateAndRun(page, templateName);
  await page.waitFor(4000);

  // Check results are there
  await auto.openLastNode(page);
  await page.waitFor(5000);

  await auto.checkDataProducedByNode(page);

  // Remove Study
  await auto.toDashboard(page);
  await auto.dashboardDeleteFirstStudy(page);

  // Make sure data was deleted

  // Log Out
  await auto.logOut(page);

  await browser.close();
}

const urls = [
  "http://localhost:9081/"
  // "http://master.osparc.io/",
  // "https://staging.osparc.io/",
  // "https://osparc.io/",
];

urls.forEach((url) => {
  runTutorial(url)
    .catch((e) => {
      console.log('Puppeteer error: ' + e);
      process.exit(1);
    });
});
