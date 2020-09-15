// node Bornstein.js [url_prefix] [template_uuid]

const tutorialBase = require('../osparc-simcore/tests/e2e/tutorials/tutorialBase');
const utils = require('../osparc-simcore/tests/e2e/utils/utils');

const args = process.argv.slice(2);
if (args.length < 1) {
  process.exit(1);
}
const URL = args[0];
const TEMPLATE_UUID = args[1];
const anonURL = URL + TEMPLATE_UUID;
const screenshotPrefix = "Bornstein_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL);

  utils.createScreenshotsDir();
  const page = await tutorial.beforeScript();
  const studyData = await tutorial.openStudyLink();

  const workbenchData = utils.extractWorkbenchData(studyData["data"]);
  await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][0]]);

  // Some time for starting the service
  await tutorial.waitFor(60000);
  await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

  // This study opens in fullscreen mode
  await tutorial.restoreIFrame();

  await tutorial.openNodeFiles(0);
  const outFiles = [
    "output.csv",
    "traces.pkl"
  ];
  await tutorial.checkResults(outFiles.length);
  await tutorial.logOut();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
