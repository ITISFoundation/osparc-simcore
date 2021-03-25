// node opencor.js [url_prefix] [template_uuid] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

const anonURL = urlPrefix + templateUuid + "?stimulation_mode=1&stimulation_level=0.5";
const screenshotPrefix = "Opencor_";


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
    await tutorial.waitForStudyDone(studyId, 30000);

    const outFiles = [
      "results.json",
      "logs.zip",
      "membrane-potential.csv"
    ];
    await tutorial.checkNodeResults(0, outFiles);
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
