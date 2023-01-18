// node Voila.js [url_prefix] [template_uuid] [start_timeout] [--demo]

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
const screenshotPrefix = "Voila";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, basicauthUsername, basicauthPassword, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log("Workbench Data:", workbenchData);
    const voilaIdViewer = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [voilaIdViewer],
      startTimeout
    );

    await tutorial.waitFor(2000, 'Service started');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    // wait for iframe to be ready, it might take a while in Voila
    const iframe = await tutorial.waitForVoilaIframe(voilaIdViewer);

    // wait for iframe to be rendered
    await tutorial.waitForVoilaRendered(iframe);
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
