// node VTK_file.js [url_prefix] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

let anonURL = urlPrefix + "/view";
const params = [
  ["file_type", "VTK"],
  ["viewer_key", "simcore/services/dynamic/3d-viewer-gpu"],
  ["viewer_version", "3.0.2"],
  ["download_link", "https://raw.githubusercontent.com/germannp/yalla/master/examples/teapot.vtk"],
  ["file_name", "teapot.vtk"],
  ["file_size", "45500"]
];
for (let i=0; i<params.length; i++) {
  const param =  params[i];
  i==0 ? anonURL += "?" : anonURL += "&";
  anonURL += param[0] + "=" + encodeURIComponent(param[1])
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
    await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][2]]);

    // Some time for starting the service
    await tutorial.waitFor(10000);
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const outFiles = [
      "data.zip"
    ];
    await tutorial.checkNodeResults(2, outFiles);
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
