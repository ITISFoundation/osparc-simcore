// node Mattward.js [url_prefix] [template_uuid] [timeout] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  startTimeout,
  basicauthUsername,
  basicauthPassword,
  enableDemoMode
} = utils.parseCommandLineArgumentsAnonymous(args);

const anonURL = urlPrefix + templateUuid;
const screenshotPrefix = "Mattward_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, basicauthUsername, basicauthPassword, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyResp = await tutorial.openStudyLink();
    const studyData = studyResp["data"];
    const studyId = studyData["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData);
    await tutorial.waitForServices(
      studyId,
      [workbenchData["nodeIds"][0]],
      startTimeout
    );

    await tutorial.waitFor(20000, 'Some time for starting the service');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    // This study opens in fullscreen mode
    await tutorial.restoreIFrame();

    const outFiles = [
      "CAP_plot.csv",
      "CV_plot.csv",
      "Lpred_plot.csv",
      "V_pred_plot.csv",
      "input.csv",
      "t_plot.csv",
      "tst_plot.csv"
    ];
    await tutorial.checkNodeOutputs(0, outFiles);
  }
  catch(err) {
    await tutorial.setTutorialFailed();
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.logOut();
    await tutorial.close();
  }

  if (tutorial.getTutorialFailed()) {
    throw "Tutorial Failed";
  }
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
