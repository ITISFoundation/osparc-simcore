// node CC_Rabbit.js [url_prefix] [template_uuid]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
if (args.length < 1) {
  process.exit(1);
}
const URL = args[0];
const TEMPLATE_UUID = args[1];
const anonURL = URL + TEMPLATE_UUID;
const screenshotPrefix = "CCRabbit_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix);

  tutorial.startScreenshooter();
  const page = await tutorial.beforeScript();
  await tutorial.goTo();

  // Some time for loading the workbench
  await tutorial.waitFor(10000);
  await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

  await tutorial.runPipeline(1500000);
  await utils.takeScreenshot(page, screenshotPrefix + 'after_1-2-3_run');

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

  await tutorial.logOut();
  tutorial.stopScreenshooter();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
