// node mattward.js [url] [user] [password] [--demo]

const utils = require('../utils/utils');
const tutorialBase = require('./tutorialBase');

const args = process.argv.slice(2);
const { url, user, pass, newUser, enableDemoMode } = utils.parseCommandLineArguments(args)

const templateName = "Mattward";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, user, pass, newUser, templateName, enableDemoMode);

  tutorial.init();
  await tutorial.beforeScript();
  await tutorial.goTo();

  await tutorial.registerIfNeeded();
  await tutorial.login();
  const studyData = await tutorial.openTemplate(1000);
  const workbenchData = utils.extractWorkbenchData(studyData["data"]);
  await tutorial.waitForService(workbenchData["studyId"], workbenchData["nodeIds"][0]);

  // Wait for the output files to be pushed
  await tutorial.waitFor(30000);

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

  await tutorial.removeStudy();
  await tutorial.logOut();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
