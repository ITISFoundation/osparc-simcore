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
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix);

  tutorial.startScreenshooter();
  const page = await tutorial.beforeScript();
  const studyData = await tutorial.openStudyLink();
  const studyId = studyData["data"]["uuid"];
  console.log("Study ID:", studyId);

  // Some time for loading the workbench
  await tutorial.waitFor(10000);
  await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

  await tutorial.runPipeline(studyId, 30000);
  await utils.takeScreenshot(page, screenshotPrefix + 'pipeline_run');

  await tutorial.openNodeFiles(0);
  const outFiles = [
    "results.json",
    "logs.zip",
    "membrane-potential.csv"
  ];
  await tutorial.checkResults(outFiles.length);

  await tutorial.logOut();
  tutorial.stopScreenshooter();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
