// node 2D_Plot.js [url_prefix] [template_uuid] [timeout] [--demo]

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
const screenshotPrefix = "2DPlot_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, basicauthUsername, basicauthPassword, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyResp = await tutorial.openStudyLink();
    const studyData = studyResp["data"];
    const studyId = studyData["uuid"];

    const rawGraphsId = utils.getNodeIdFromServiceKey(studyData["workbench"], "raw-graphs");
    await tutorial.waitForServices(
      studyId,
      [rawGraphsId],
      startTimeout
    );

    await tutorial.waitFor(5000, 'Some time for starting the service');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame0');

    const frame = await tutorial.getIframe(rawGraphsId);

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
