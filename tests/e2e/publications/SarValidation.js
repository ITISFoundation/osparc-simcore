// node SarValidation.js [url_prefix] [template_uuid] [start_timeout] [--demo]

// master https://osparc-master.speag.com/study/2b7b88be-ea51-11ed-ade4-02420a000d13
// prod https://osparc.io/study/ff72c36a-df81-11ed-9c9e-02420a0b755a

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
const screenshotPrefix = "SarValidation";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, basicauthUsername, basicauthPassword, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log("Workbench Data:", workbenchData);
    const sarIdViewer = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [sarIdViewer],
      startTimeout,
      false
    );

    await tutorial.waitFor(5000, 'Service started');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const sarIframe = await tutorial.getIframe(sarIdViewer);
    await tutorial.testSARValidation(sarIframe);
  }
  catch(err) {
    await tutorial.setTutorialFailed(true, false);
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
