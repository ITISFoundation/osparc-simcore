// node isolve-gpu.js [url] [user] [password] [--demo]

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
  let studyId
  try {
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    await tutorial.waitFor(5000, 'Some time for loading the workbench');

    await tutorial.runPipeline();
    await tutorial.waitForStudyDone(studyId, 30000);

    const outFiles = [
      "logs.zip",
      "output.h5",
      "log.tgz"
    ];
    await tutorial.openNodeFiles(1)
    await tutorial.checkResults2(outFiles);
  }
  catch(err) {
    tutorial.setTutorialFailed(true);
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
