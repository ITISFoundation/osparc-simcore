// node CC_Human.js [url_prefix] [template_uuid]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
if (args.length < 1) {
  process.exit(1);
}
const URL = args[0];
const TEMPLATE_UUID = args[1];
const anonURL = URL + TEMPLATE_UUID;
const screenshotPrefix = "CCHuman_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix);

  tutorial.startScreenshooter();
  const page = await tutorial.beforeScript();
  const studyData = await tutorial.openStudyLink();
  const studyId = studyData["data"]["uuid"];
  console.log("Study ID:", studyId);

  // Some time for loading the workbench
  await tutorial.waitFor(10000);
  await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

  await tutorial.runPipeline(studyId, 1800000);
  await utils.takeScreenshot(page, screenshotPrefix + 'after_1-2-3_run');

  await tutorial.openNodeFiles(1);
  const outFiles0 = [
    "vm_1Hz.txt",
    "logs.zip",
    "allresult_1Hz.txt"
  ];
  await tutorial.checkResults(outFiles0.length);

  await tutorial.openNodeFiles(2);
  const outFiles1 = [
    "model_INPUT.from1D",
    "y_1D.txt",
    "logs.zip",
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

  await tutorial.logOut();
  tutorial.stopScreenshooter();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
