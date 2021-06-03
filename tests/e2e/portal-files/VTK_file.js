// node VTK_file.js [url] [download_link] [file_size] [--demo]

const fetch = require('node-fetch');
const tutorialBase = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  params,
  enableDemoMode
} = utils.parseCommandLineArgumentsStudyDispatcherParams(args);

const fileType = "VTK"
const screenshotPrefix = fileType + "_file_";


async function runTutorial () {
  const urlViewers = urlPrefix + "/v0/viewers/default";
  const response = await fetch(urlViewers);
  const viewers = await response.json();
  const viewer = viewers["data"].find(viewer => viewer.file_type === fileType)
  console.log(viewer.view_url);

  const urlParams = new URLSearchParams(viewer.view_url);
  for (const [key, value] of urlParams.entries()) {
    console.log(key, value);
  }
  let anonURL = encodeURI(viewer.view_url);
  for (let i=0; i<Object.keys(params).length; i++) {
    const paramKey =  Object.keys(params)[i];
    const paramValue =  params[paramKey];
    anonURL += "&" + paramKey + "=" + paramValue
  }

  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    const nodeIdViewer = workbenchData["nodeIds"][1];
    await tutorial.waitForServices(workbenchData["studyId"], [nodeIdViewer]);

    // Some time for starting the service
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const iframeHandles = await page.$$("iframe");
    const iframes = [];
    for (let i=0; i<iframeHandles.length; i++) {
      const frame = await iframeHandles[i].contentFrame();
      iframes.push(frame);
    }
    // url/x/nodeIdViewer
    const frame = iframes.find(iframe => iframe._url.includes(nodeIdViewer));

    // inside the iFrame, click on document icon on top
    const docSelector = '/html/body/div/div/div[1]/div[1]/div[2]/div[1]/div[1]/i[2]';
    const docElements = await frame.$x(docSelector);
    await docElements[0].click();

    // then click on the file to render it
    const fileSelector = '/html/body/div/div/div[1]/div[1]/div[2]/div[2]/div/ul[2]';
    const fileElements = await frame.$x(fileSelector);
    await fileElements[0].click();

    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'teapot');
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
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
