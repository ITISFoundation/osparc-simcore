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

    const mattwardViewerId = utils.getNodeIdFromServiceKey(studyData["workbench"], "mattward-viewer");
    if (!mattwardViewerId) {
      throw new Error('Could not find node with service key "mattward-viewer"');
    }
    await tutorial.waitForServices(
      studyId,
      [mattwardViewerId],
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
