// node VTK_file.js [url_prefix] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  params,
  enableDemoMode
} = utils.parseCommandLineArgumentsStudyDispatcherParams(args);

let anonURL = urlPrefix + "/view";
for (let i=0; i<Object.keys(params).length; i++) {
  const paramKey =  Object.keys(params)[i];
  const paramValue =  params[paramKey];
  i==0 ? anonURL += "?" : anonURL += "&";
  anonURL += paramKey[0] + "=" + paramValue
}
const screenshotPrefix = "VTK_file_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
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
