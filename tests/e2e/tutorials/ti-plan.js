// node ti-plan.js [url] [user] [password] [--demo]

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

const studyName = "New Plan";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, studyName, user, pass, newUser, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();

    // check that the "New Study" is "New Plan"
    await tutorial.checkFirstStudyId("newPlanButton");

    // create New Plan
    const studyData = await tutorial.startNewPlan();
    studyId = studyData["data"]["uuid"];

    // check the app mode steps
  }
  catch (err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
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
