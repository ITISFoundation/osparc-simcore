// node opencor.js [url_prefix] [template_uuid]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
if (args.length < 1) {
  process.exit(1);
}
const URL = args[0];
const TEMPLATE_UUID = args[1];
const anonURL = URL + TEMPLATE_UUID + "?stimulation_mode=1&stimulation_level=0.5";
const screenshotPrefix = "Opencor_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL);

  tutorial.initScreenshoter();
  const page = await tutorial.beforeScript();
  await tutorial.goTo();

  // Some time for loading the workbench
  await tutorial.waitFor(10000);
  await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

  await tutorial.runPipeline(30000);
  await utils.takeScreenshot(page, screenshotPrefix + 'pipeline_run');

  await tutorial.openNodeFiles(0);
  const outFiles = [
    "results.json",
    "logs.zip",
    "membrane-potential.csv"
  ];
  await tutorial.checkResults(outFiles.length);

  await tutorial.logOut();
  tutorial.stopScreenshoter();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
