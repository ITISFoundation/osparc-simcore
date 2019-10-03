// node sleepers.js [user] [password]

const startBrowser = require('../utils/startBrowser');
const auto = require('../utils/auto');
const utils = require('../utils/utils');

const demo = false;

let user = null;
let pass = null;
let newUser = true;
const args = process.argv.slice(2);
if (args.length === 2) {
  user = args[0];
  pass = args[1];
  newUser = false;
}

if (newUser) {
  const userPass = utils.getRandUserAndPass();
  user = userPass.user;
  pass = userPass.pass;
}

async function runTutorial (url) {
  console.log("Running tutorial on", url);
  const browser = await startBrowser.launch(demo);
  const page = await browser.newPage();
  await page.goto(url);

  if (newUser) {
    await auto.register(page, user, pass);
  }
  // Login
  await auto.logIn(page, user, pass);

  // Use template to create Sleepers study
  await utils.waitForResponse(page, "projects?type=template");
  // Run pipeline
  const templateName = "Sleepers";
  await auto.dashboardOpenFirstTemplateAndRun(page, templateName);
  const timeForFirstNodeToFinish = 20000;
  await page.waitFor(timeForFirstNodeToFinish);

  // Check results are there
  await auto.openNode(page, 0);

  try {
    await auto.checkDataProducedByNode(page);
  }
  catch(err) {
    console.log("Failed checking Data Produced By Node", err);
  }

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
