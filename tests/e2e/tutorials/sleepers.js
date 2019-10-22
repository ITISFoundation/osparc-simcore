// node sleepers.js [user] [password]

const startBrowser = require('../utils/startBrowser');
const auto = require('../utils/auto');
const utils = require('../utils/utils');
const responses = require('../utils/responsesQueue');

const demo = false;

const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Expected at least url argument!');
  process.exit(1);
}
const url = args[0];
let user = null;
let pass = null;
let newUser = true;
if (args.length === 3) {
  user = args[1];
  pass = args[2];
  newUser = false;
} else {
  const userPass = utils.getRandUserAndPass();
  user = userPass.user;
  pass = userPass.pass;
}

async function runTutorial (url) {
  console.log("Running tutorial on", url);
  const browser = await startBrowser.launch(demo);
  const page = await browser.newPage();
  await page.goto(url);

  const responsesQueue = new responses.ResponsesQueue(page);

  if (newUser) {
    await auto.register(page, user, pass);
  }
  // Login
  responsesQueue.addResponseListener("projects?type=template");
  await auto.logIn(page, user, pass);

  // Use template to create Sleepers study
  try {
    await responsesQueue.waitUntilResponse("projects?type=template");
  }
  catch(err) {
    console.error(err);
  }

  // Run pipeline
  const templateName = "Sleepers";
  await auto.dashboardOpenFirstTemplate(page, templateName);
  const timeForFirstNodeToFinish = 20000;
  await auto.runStudy(page, timeForFirstNodeToFinish);

  // Check results are there
  await auto.openNode(page, 0);

  try {
    await auto.checkDataProducedByNode(page);
  }
  catch(err) {
    console.error("Failed checking Data Produced By Node", err);
  }

  // Remove Study
  await auto.toDashboard(page);
  await auto.dashboardDeleteFirstStudy(page);

  // Make sure data was deleted

  // Log Out
  await auto.logOut(page);

  await browser.close();
}

runTutorial(url)
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });