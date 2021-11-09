// node Voila.js [url_prefix] [template_uuid] [--demo]

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
const screenshotPrefix = "Voila_";


async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(anonURL, screenshotPrefix, null, null, null, enableDemoMode);

  try {
    const page = await tutorial.beforeScript();
    const studyData = await tutorial.openStudyLink();
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    const voilaIdViewer = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(workbenchData["studyId"], [voilaIdViewer]);

    await tutorial.waitFor(20000, 'Some time for starting the service');
    await utils.takeScreenshot(page, screenshotPrefix + 'service_started');

    const iframeHandles = await page.$$("iframe");
    const iframes = [];
    for (let i=0; i<iframeHandles.length; i++) {
      const frame = await iframeHandles[i].contentFrame();
      iframes.push(frame);
    }
    // url/x/voilaIdViewer
    const frame = iframes.find(iframe => iframe._url.includes(voilaIdViewer));

    // check the title says "VISUALIZATION"
    const titleSelector = '#VISUALIZATION';
    await frame.waitForSelector(titleSelector);
    const titleText = await page.evaluate(() => {
      const element = document.querySelector(titleSelector);
      return element ? element.innerText : null;
    });
    if (titleText !== "VISUALIZATION") {
      throw new Error("Voila page title doesn't match the expected");
    }
    await utils.takeScreenshot(page, screenshotPrefix + 'iFrame1');
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.logOut();
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
