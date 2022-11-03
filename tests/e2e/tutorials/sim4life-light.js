// node ti-plan.js [url] [user] [password] [timeout] [--demo]

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

const studyName = "S4L_light";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, studyName, user, pass, newUser, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();

    // make sure only sim4life-dy is available
    const services = tutorial.getReceivedServices();
    if (services.length && services.every(service => service.key === "simcore/services/dynamic/sim4life-dy")) {
      console.log("Expected services received");
    }
    else {
      throw "Check exposed services";
    }

    // start Sim4Life Light
    const studyData = await tutorial.startSim4LifeLight();
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
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
    throw "Tutorial Failed";
  }
  finally {
    if (studyId) {
      await tutorial.toDashboard()
      await tutorial.removeStudy(studyId, 20000);
    }
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
