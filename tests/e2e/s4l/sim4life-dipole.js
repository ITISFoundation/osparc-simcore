// node sim4life-dipole.js [url] [--user user] [--pass password] [--start_timeout timeout] [--demo]

const utils = require('../utils/utils');
const tutorialBase = require('../tutorials/tutorialBase');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  newUser,
  startTimeout,
  basicauthUsername,
  basicauthPassword,
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const tutorialName = "Dipole Antenna";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, tutorialName, user, pass, newUser, basicauthUsername, basicauthPassword, enableDemoMode);
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
    const studyData = await tutorial.openTemplate();
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

    await tutorial.testS4LDipole(s4lNodeId);
  }
  catch (err) {
    tutorial.setTutorialFailed(err);
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

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
