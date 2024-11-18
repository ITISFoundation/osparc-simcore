// node Kember.js [url_prefix] [template_uuid] [timeout] [--demo]

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
const screenshotPrefix = "Kember_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, basicauthUsername, basicauthPassword, enableDemoMode);

  try {
    await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    const kemberSolver = workbenchData["nodeIds"][0];
    const kemberIdViewer = workbenchData["nodeIds"][1];

    await tutorial.takeScreenshot("template_started");

    // check the app mode steps
    const appModeSteps = await tutorial.getAppModeSteps();
    if (appModeSteps.length !== 2) {
      throw "Two steps expected, got " + appModeSteps;
    }

    // Run solver
    await tutorial.waitAndClick("AppMode_RunBtn");
    await tutorial.waitFor(5000, "Running Solver");
    await tutorial.takeScreenshot("solver_before");
    await tutorial.waitForStudyDone(studyId, startTimeout);
    await tutorial.takeScreenshot("solver_after");
    await tutorial.waitFor(2000, "Solver Finished");

    const outFiles = [
      "logs.zip",
      "outputController.dat"
    ];
    await tutorial.checkNodeOutputsAppMode(kemberSolver, outFiles, true);


    // open kember viewer
    await tutorial.waitAndClick("AppMode_NextBtn");
    await tutorial.takeScreenshot("viewer_before");
    await tutorial.waitFor(2000);
    // wait for iframe to be ready, it might take a while in Voila
    const iframe = await tutorial.waitForVoilaIframe(kemberIdViewer);
    // wait for iframe to be rendered
    await tutorial.waitForVoilaRendered(iframe);
    await tutorial.takeScreenshot("viewer_after");
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
