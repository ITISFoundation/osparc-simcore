// node sim4life-lite.js [url] [user] [password] [timeout] [--demo]

const utils = require('../utils/utils');
const tutorialBase = require('../tutorials/tutorialBase');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  newUser,
  startTimeout,
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const studyName = "sim4life";

async function runTutorial(url, studyName, user, pass, newUser, enableDemoMode) {
  const tutorial = new tutorialBase.TutorialBase(url, studyName, user, pass, newUser, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();

    // make sure only sim4life-lite is available
    const services = tutorial.getReceivedServices();
    if (services.length && services.every(service => service.key === "simcore/services/dynamic/sim4life-lite")) {
      console.log("Expected services received");
    }
    else {
      throw "Check exposed services";
    }

    // start Sim4Life Lite
    const studyData = await tutorial.startSim4LifeLite();
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

    await tutorial.testS4L(s4lNodeId);
  }
  catch (err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
    throw "Tutorial Failed";
  }
  finally {
    await tutorial.leave(studyId);
  }

  if (tutorial.getTutorialFailed()) {
    throw "Tutorial Failed";
  }
}

runTutorial(url, studyName, user, pass, newUser, enableDemoMode)
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
