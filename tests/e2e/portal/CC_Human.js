// node CC_Human.js [url_prefix] [template_uuid] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

const anonURL = urlPrefix + templateUuid;
const screenshotPrefix = "CCHuman_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    await tutorial.waitFor(10000, 'Some time for loading the workbench');
    await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

    await tutorial.runPipeline();
    await tutorial.waitForStudyDone(studyId, 1800000);

    const outFiles0 = [
      "vm_1Hz.txt",
      "logs.zip",
      "allresult_1Hz.txt"
    ];
    await tutorial.openNodeFiles(1)
    await tutorial.checkResults2(outFiles0);

    const outFiles1 = [
      "model_INPUT.from1D",
      "y_1D.txt",
      "logs.zip",
      "ECGs.txt"
    ];
    await tutorial.openNodeFiles(2)
    await tutorial.checkResults2(outFiles1);

    const outFiles2 = [
      "aps.zip",
      "logs.zip"
    ];
    await tutorial.openNodeFiles(3)
    await tutorial.checkResults2(outFiles2);
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
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
