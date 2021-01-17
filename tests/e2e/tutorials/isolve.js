// node isolve.js [url] [user] [password] [--demo]

// https://itisfoundation.github.io/osparc-manual-z43/#/Tutorials/GeneralTutorial

const utils = require('../utils/utils');
const tutorialBase = require('./tutorialBase');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  newUser,
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const templateName = "isolve-gpu";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    await tutorial.start();
    const studyData = await tutorial.openService(1000);
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    // Some time for loading the workbench
    await tutorial.waitFor(5000);

    await tutorial.runPipeline(studyId, 60000);
    console.log('Checking isolve results:');
    await tutorial.openNodeFiles(1);
    const outFiles = [
      "output.h5",
      "log.tgz"
    ];
    await tutorial.checkResults(outFiles.length);

    await tutorial.toDashboard();

    await tutorial.removeStudy(studyId);
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
