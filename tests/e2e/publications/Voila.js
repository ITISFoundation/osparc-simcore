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
const screenshotPrefix = "Voila";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

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

    const voilaTimeout = 240000;
    const checkFrequency = 5000;
    // wait for iframe to be ready, it might take a while in Voila
    let iframe = null;
    for (let i=0; i<voilaTimeout; i+=checkFrequency) {
      iframe = await tutorial.getIframe(voilaIdViewer);
      if (iframe) {
        break;
      }
      await tutorial.waitFor(checkFrequency, `iframe not ready yet: ${i/1000}s`);
    }

    // Voila says: "Ok, voila is still executing...". At this point we can only wait
    await tutorial.waitFor(50000, "Load iframe");
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame');

    // look for "rendered_cells" which is the root div of a Voila document
    await iframe.waitForSelector('#rendered_cells', {
      timeout: 5000
    })
      .then(() => console.log("Voila started successfully"))
      .catch(() => console.log("Voila page not found"));
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
