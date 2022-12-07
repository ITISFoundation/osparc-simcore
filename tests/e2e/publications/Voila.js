// node Voila.js [url_prefix] [template_uuid] [start_timeout] [--demo]

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
const screenshotPrefix = "Nature_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log("Workbench Data:", workbenchData);
    const voilaIdViewer = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(workbenchData["studyId"], [voilaIdViewer], startTimeout);

    await tutorial.waitFor(40000, 'Some time for starting the iframe');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const iframe = await tutorial.getIframe(voilaIdViewer);
    // look for rendered_cells
    const rendered_cells = iframe.querySelector('#rendered_cells');
    console.log(rendered_cells);
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame');
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
