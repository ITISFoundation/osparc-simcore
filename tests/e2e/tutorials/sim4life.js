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

const templateName = "sim4life";


async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);
  let studyId

  try {
    await tutorial.start();
    const studyData = await tutorial.openService(1000);
    studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log(workbenchData);
    await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][0]], startTimeout);

    await tutorial.waitFor(12000, 'Wait for some time');
  }
  catch(err) {
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
