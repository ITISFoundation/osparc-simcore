// node 2D_Plot.js [url_prefix] [template_uuid] [--demo]

const tutorialBase = require('../tutorials/tutorialBase');
const auto = require('../utils/auto');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  urlPrefix,
  templateUuid,
  enableDemoMode
} = utils.parseCommandLineArgumentsTemplate(args);

const anonURL = urlPrefix + templateUuid;
const screenshotPrefix = "2DPlot_";


async function runTutorial () {
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
    await tutorial.waitFor(5000);
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    // await tutorial.openNode(1);
    auto.openNode(page, 1);

    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame0');

    const iframeHandles = await page.$$("iframe");
    const iframes = [];
    for (let i=0; i<iframeHandles.length; i++) {
      const frame = await iframeHandles[i].contentFrame();
      iframes.push(frame);
    }
    // url/x/nodeIdViewer
    const frame = iframes.find(iframe => iframe._url.includes(nodeIdViewer));

    // inside the iFrame, click on "oSPARC inputs"
    const oSPARCInputsSelector = '#load-data > div > div:nth-child(2) > div.col-lg-2 > ul > li:nth-child(5)';
    await frame.waitForSelector(oSPARCInputsSelector);
    await frame.click(oSPARCInputsSelector);
    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame1');

    // after click on "oSPARC inputs", click on the input coming from the File Picker
    const oSPARCInputSelector = '#load-data > div > div:nth-child(2) > div.col-lg-10 > div:nth-child(8) > div';
    await frame.waitForSelector(oSPARCInputSelector);
    await frame.click(oSPARCInputSelector);
    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame2');
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
