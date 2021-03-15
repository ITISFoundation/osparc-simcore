// node kember.js [url_prefix] [template_uuid] [--demo]

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
const screenshotPrefix = "Kember_";


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

    // Some time for loading the workbench
    await tutorial.waitFor(10000);
    await utils.takeScreenshot(page, screenshotPrefix + 'workbench_loaded');

    await tutorial.runPipeline();
    await tutorial.waitForStudyDone(studyId, 120000);

    const outFiles = [
      "logs.zip",
      "outputController.dat"
    ];
    await tutorial.checkNodeResults(0, outFiles);


    // open kember viewer
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

    // restart kernel: click restart and accept
    const restartSelector = "#run_int > button:nth-child(3)";
    await frame.waitForSelector(restartSelector);
    await frame.click(restartSelector);
    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'restart_pressed');
    const acceptSelector = "body > div.modal.fade.in > div > div > div.modal-footer > button.btn.btn-default.btn-sm.btn-danger";
    await frame.waitForSelector(acceptSelector);
    await frame.click(acceptSelector);
    await tutorial.waitFor(2000);
    await utils.takeScreenshot(page, screenshotPrefix + 'restart_accept');

    await tutorial.waitFor(20000);
    await utils.takeScreenshot(page, screenshotPrefix + 'notebook_run');

    // check output
    const outFiles2 = [
      "Hear_Rate.csv",
      "notebooks.zip",
      "Parasympathetic_Cell_Activity.csv",
      "Table_Data.csv"
    ];
    await tutorial.checkNodeResults(1, outFiles2);
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
