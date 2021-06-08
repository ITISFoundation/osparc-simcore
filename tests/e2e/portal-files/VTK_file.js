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
  const viewer = viewers["data"].find(viewer => viewer.file_type === fileType);

  const url = new URL(viewer.view_url);

  // append the command line arguments
  Object.entries(params).forEach(entry => {
    const [key, value] = entry;
    url.searchParams.append(key, value);
  });

  const tutorial = new tutorialBase.TutorialBase(url.toString(), screenshotPrefix, null, null, null, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    const nodeIdViewer = workbenchData["nodeIds"][1];
    await tutorial.waitForServices(workbenchData["studyId"], [nodeIdViewer]);
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    // Some time for setting up service's frontend
    await tutorial.waitFor(3000);

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
