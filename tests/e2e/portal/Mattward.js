// node Mattward.js [url_prefix] [template_uuid]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
if (args.length < 1) {
  process.exit(1);
}
const URL = args[0];
const TEMPLATE_UUID = args[1];
const anonURL = URL + TEMPLATE_UUID;
const screenshotPrefix = "Mattward_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL);

  utils.createScreenshotsDir();
  const page = await tutorial.beforeScript();
  const studyData = await tutorial.openStudyLink();

  const workbenchData = utils.extractWorkbenchData(studyData["data"]);
  await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][0]]);

  // Some time for starting the service
  await tutorial.waitFor(20000);
  await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

  // This study opens in fullscreen mode
  await tutorial.restoreIFrame();

  await tutorial.openNodeFiles(0);
  const outFiles = [
    "CAP_plot.csv",
    "CV_plot.csv",
    "Lpred_plot.csv",
    "V_pred_plot.csv",
    "input.csv",
    "t_plot.csv",
    "tst_plot.csv"
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
