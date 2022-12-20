// node sim4life.js [url] [user] [password] [timeout] [--demo]

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
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const serviceName = "sim4life-dy";

async function runTutorial(user, pass, newUser, parallelUserIdx) {
  const tutorial = new tutorialBase.TutorialBase(url, serviceName, user, pass, newUser, enableDemoMode, parallelUserIdx);
  let studyId;
  try {
    await tutorial.start();

    // start sim4life-dy service
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

    // NOTE: we do not test anything but service being ready here
  }
  catch (err) {
    await tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
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
  for (let i = 1; i <= nUsers; i++) {
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
