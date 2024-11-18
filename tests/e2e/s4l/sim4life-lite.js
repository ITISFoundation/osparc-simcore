// node sim4life-lite.js [url] [--user user] [--pass password] [--start_timeout timeout] [--demo]

const utils = require('../utils/utils');
const tutorialBase = require('../tutorials/tutorialBase');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  newUser,
  nUsers,
  userPrefix,
  userSuffix,
  startTimeout,
  basicauthUsername,
  basicauthPassword,
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const studyName = "New project";

async function runTutorial(user, pass, newUser, parallelUserIdx) {
  const tutorial = new tutorialBase.TutorialBase(
    url,
    studyName,
    user,
    pass,
    newUser,
    basicauthUsername,
    basicauthPassword,
    enableDemoMode,
    parallelUserIdx
  );
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

    await utils.sleep(2000, "Wait for Quick Start dialog");
    await tutorial.closeQuickStart();

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
    await tutorial.setTutorialFailed();
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

let credentials = [{
  user,
  pass
}];
if (nUsers && userPrefix && userSuffix && pass) {
  credentials = [];
  for (let i=1; i<=nUsers; i++) {
    // it will only work from 01 to 99
    const id = ("0" + i).slice(-2);
    credentials.push({
      user: userPrefix + id + userSuffix,
      pass: pass
    });
  }
}

credentials.forEach((credential, idx) => {
  runTutorial(credential.user, credential.pass, newUser, idx)
    .catch(error => {
      console.log('Puppeteer error: ' + error);
      process.exit(1);
    });
});
