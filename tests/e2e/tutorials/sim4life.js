// node sim4life.js [url] [user] [password] [--demo]

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

const serviceName = "sim4life-dy";


async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, serviceName, user, pass, newUser, enableDemoMode);
  let studyId

  try {
    await tutorial.start();
    const studyData = await tutorial.openService(1000);
    studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log(workbenchData);
    const s4lNodeId = workbenchData["nodeIds"][0];
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [s4lNodeId],
      startTimeout,
      false
    );

    await tutorial.waitFor(15000, 'Wait for some time');

    // do some basic interaction
    const s4lIframe = await tutorial.getIframe(s4lNodeId);
    const modelTree = await s4lIframe.$('.model-tree');
    const modelItems = await modelTree.$$('.MuiTreeItem-label');
    const nLabels = modelItems.length;
    if (nLabels > 1) {
      modelItems[0].click();
      await tutorial.waitFor(2000, 'Model clicked');
      await tutorial.takeScreenshot('ModelClicked');
      modelItems[1].click();
      await tutorial.waitFor(2000, 'Grid clicked');
      await tutorial.takeScreenshot('GridlClicked');
    }
  }
  catch (err) {
    await tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.toDashboard()
    await tutorial.removeStudy(studyId);
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
