// node CC_Rabbit.js [url_prefix] [template_uuid] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

const anonURL = urlPrefix + templateUuid;
const screenshotPrefix = "CCRabbit_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    // Some time for loading the workbench
    await tutorial.waitFor(10000);
    await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

    await tutorial.runPipeline();
    await tutorial.waitForStudyDone(studyId, 1500000);

    await tutorial.openNodeFiles(1);
    const outFiles0 = [
      "logs.zip",
      "allresult_1Hz.txt",
      "vm_1Hz.txt"
    ];
    await tutorial.checkResults(outFiles0.length);

    await tutorial.openNodeFiles(2);
    const outFiles1 = [
      "model_INPUT.from1D",
      "logs.zip",
      "cai_1D.txt",
      "ap_1D.txt",
      "ECGs.txt"
    ];
    await tutorial.checkResults(outFiles1.length);

    await tutorial.openNodeFiles(3);
    const outFiles2 = [
      "aps.zip",
      "logs.zip"
    ];
    await tutorial.checkResults(outFiles2.length);

    // await tutorial.openNodeRetrieveAndRestart(4);
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.logOut();
    tutorial.stopScreenshooter();
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
