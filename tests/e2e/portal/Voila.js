// node Voila.js [url_prefix] [template_uuid] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  startTimeout,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

const anonURL = urlPrefix + templateUuid;
const screenshotPrefix = "Voila_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log("Workbench Data:", workbenchData);
    const voilaIdViewer = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(workbenchData["studyId"], [voilaIdViewer], startTimeout);

    await tutorial.waitFor(40000, 'Some time for starting the service');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const frame = tutorial.getIframe(voilaIdViewer);

    // check title says "VISUALIZATION"
    const titleSelector = '#VISUALIZATION';
    const element = await frame.$(titleSelector);
    const titleText = await frame.evaluate(el => el.innerText, element);
    console.log("titleText", titleText);
    if (titleText !== "VISUALIZATION") {
      throw new Error("Voila page title doesn't match the expected");
    }
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame1');
  }
  catch(err) {
    await tutorial.setTutorialFailed(true);
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
