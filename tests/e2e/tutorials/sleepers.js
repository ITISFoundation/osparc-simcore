// node sleepers.js [url] [user] [password]
const fs = require('fs');

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
const templateName = "Sleepers";

async function runTutorial (url) {
  console.log("Running tutorial on", url);
  const browser = await startBrowser.launch(demo);
  const page = await browser.newPage();
  await page.setViewport({
    width:1920,
    height:1080
  });

  // Try to reach the website
  try {
    await page.goto(url);
  }
  catch(err) {
    console.error(url, "can't be reached", err);
  }

  url = url.replace("http://", "");
  url = url.replace("https://", "");
  url = url.substr(0, url.indexOf("/")); 
  await utils.takeScreenshot(page, templateName + "_landingPage_" + url);

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
    console.error("Templates could not be fetched", err);
  }

  // Open template
  await utils.takeScreenshot(page, templateName + "_dashboardOpenFirstTemplate_before");
  responsesQueue.addResponseListener("projects?from_template=");
  try {
    await auto.dashboardOpenFirstTemplate(page, templateName);
    await responsesQueue.waitUntilResponse("projects?from_template=");
  }
  catch(err) {
    console.error(templateName, "could not be started", err);
  }
  await page.waitFor(1000);
  await utils.takeScreenshot(page, templateName + "_dashboardOpenFirstTemplate_after");

  // Some time for loading the workbench
  await page.waitFor(5000);

  // Run pipeline
  await utils.takeScreenshot(page, templateName + "_runStudy_before");
  const timeForFirstNodeToFinish = 25000;
  await auto.runStudy(page, timeForFirstNodeToFinish);
  await utils.takeScreenshot(page, templateName + "_runStudy_after");

  // Check results are there
  await auto.openNode(page, 0);

  responsesQueue.addResponseListener("storage/locations/0/files/metadata?uuid_filter=");
  await auto.openNodeFiles(page);
  try {
    await responsesQueue.waitUntilResponse("storage/locations/0/files/metadata?uuid_filter=");
  }
  catch(err) {
    console.error(err);
  }

  await utils.takeScreenshot(page, templateName + "_checkResults_before");
  try {
    await auto.checkDataProducedByNode(page);
  }
  catch(err) {
    console.error("Failed checking Data Produced By Node", err);
  }
  await utils.takeScreenshot(page, templateName + "_checkResults_after");

  // Remove Study
  await auto.toDashboard(page);
  await utils.takeScreenshot(page, templateName + "_dashboardDeleteFirstStudy_before");
  responsesQueue.addResponseListener("projects/");
  await auto.dashboardDeleteFirstStudy(page);
  try {
    await responsesQueue.waitUntilResponse("projects/");
  }
  catch(err) {
    console.error("Failed deleting study", err);
  }
  await utils.takeScreenshot(page, templateName + "_dashboardDeleteFirstStudy_after");

  // TODO: Make sure data was deleted

  // Log Out
  await auto.logOut(page);

  await browser.close();
}

dir = 'screenshots';
if (!fs.existsSync(dir)){
  fs.mkdirSync(dir);
}

runTutorial(url)
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });