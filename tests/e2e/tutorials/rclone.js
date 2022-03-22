// node rclone.js [url] [user] [password] [--demo]

const utils = require('../utils/utils');
const tutorialBase = require('./tutorialBase');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  newUser,
  startTimeout,
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const studyName = "rclone e2e";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, studyName, user, pass, newUser, enableDemoMode);
  try {
    await tutorial.start();
    const studyData = await tutorial.openStudy(1000);
    const workbenchData = utils.extractWorkbenchData(studyData["data"]);

    const nServices = 10;
    const nodeIds = [];
    for (let i=0; i<nServices; i++) {
      nodeIds.push(workbenchData["nodeIds"][i]);
    }
    await tutorial.waitForServices(workbenchData["studyId"], nodeIds, startTimeout);
    await tutorial.waitFor(2000);

    // run all cells in parallel
    for (let i=0; i<nServices; i++) {
      await tutorial.openNode(i);

      const iframeHandles = await tutorial.getIframe();
      const iframes = [];
      for (let i = 0; i < iframeHandles.length; i++) {
        const frame = await iframeHandles[i].contentFrame();
        iframes.push(frame);
        console.log(i, frame._url);
      }

      const jLabIframes = iframes.filter(iframe => iframe._url.includes("/lab"));
      if (jLabIframes.length) {
        const jLabIframe = jLabIframes[jLabIframes.length - 1]
        await utils.runAllCellsInJupyterLab(tutorial.getPage(), jLabIframe, "test_rclone.ipynb");
      }
    }

    // wait for some time until all cells are executed
    tutorial.waitFor(10000, "wait for cell executions");

    // search matches, tw0 per service
    const findWord = "finished";
    const matches = await page.evaluate((findWord) => {
      let matches = 0;
      while (window.find(findWord)) {
        matches++;
      }
      return matches;
    }, findWord);
    console.log("found", matches)
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.toDashboard()
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
