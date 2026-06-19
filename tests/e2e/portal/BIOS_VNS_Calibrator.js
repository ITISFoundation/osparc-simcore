// node BIOS_VNS_Calibrator.js [url_prefix] [template_uuid] [timeout] [--demo]

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
const screenshotPrefix = "BIOS_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, basicauthUsername, basicauthPassword, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyResp = await tutorial.openStudyLink();
    const studyData = studyResp["data"];
    const studyId = studyData["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData);
    console.log("Workbench Data:", workbenchData);
    const BIOSIdViewer = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(
      studyId,
      [BIOSIdViewer],
      startTimeout,
      false
    );

    await tutorial.waitFor(5000, 'Some time for starting the service');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    // This study opens in fullscreen mode
    await tutorial.restoreIFrame();
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
