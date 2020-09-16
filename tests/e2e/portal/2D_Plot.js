// node 2D_Plot.js [url_prefix] [template_uuid]

const tutorialBase = require('../osparc-simcore/tests/e2e/tutorials/tutorialBase');
const auto = require('../osparc-simcore/tests/e2e/utils/auto');
const utils = require('../osparc-simcore/tests/e2e/utils/utils');

const args = process.argv.slice(2);
if (args.length < 1) {
  process.exit(1);
}
const URL = args[0];
const TEMPLATE_UUID = args[1];
const anonURL = URL + TEMPLATE_UUID;
const screenshotPrefix = "2DPlot_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL);

  utils.createScreenshotsDir();
  const page = await tutorial.beforeScript();
  const studyData = await tutorial.openStudyLink();

  const workbenchData = utils.extractWorkbenchData(studyData["data"]);
  await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][1]]);

  // Some time for starting the service
  await tutorial.waitFor(5000);
  await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

  // await tutorial.openNode(1);
  auto.openNode(page, 1);

  await tutorial.waitFor(2000);
  await utils.takeScreenshot(page, screenshotPrefix + 'iFrame0');

  const iframeHandles = await page.$$("iframe");
  // expected two iframes = loading + raw-graph
  const frame = await iframeHandles[1].contentFrame();

  // inside the iFrame, click on "oSPARC inputs"
  const oSPARCInputsSelector = '#load-data > div > div:nth-child(2) > div.col-lg-2 > ul > li:nth-child(5)';
  await frame.waitForSelector(oSPARCInputsSelector);
  await frame.click(oSPARCInputsSelector);
  await tutorial.waitFor(2000);
  await utils.takeScreenshot(page, screenshotPrefix + 'iFrame1');

  // after click on "oSPARC inputs", click on the input coming from the File Picker
  const oSPARCInputSelector = '#load-data > div > div:nth-child(2) > div.col-lg-10 > div:nth-child(8) > div';
  await frame.waitForSelector(oSPARCInputSelector);
  await frame.click(oSPARCInputSelector);
  await tutorial.waitFor(2000);
  await utils.takeScreenshot(page, screenshotPrefix + 'iFrame2');

  await tutorial.logOut();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
