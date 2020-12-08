// node 3D_Anatomical.js [url_prefix] [template_uuid] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

const anonURL = urlPrefix + templateUuid;
const screenshotPrefix = "3DAnatomical_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  tutorial.startScreenshooter();
  const page = await tutorial.beforeScript();
  const studyData = await tutorial.openStudyLink();
  const studyId = studyData["data"]["uuid"];
  console.log("Study ID:", studyId);

  const workbenchData = utils.extractWorkbenchData(studyData["data"]);
  await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][1]]);

  // Some time for starting the service
  await tutorial.waitFor(10000);
  await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

  await tutorial.openNodeFiles(1);
  const outFiles = [
    "data.zip"
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
