// node sleepers.js [url] [user] [password] [--demo]

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

const templateName = "Sleepers";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    console.log("Study ID:", studyData["data"]["uuid"]);

    // Some time for loading the workbench
    await tutorial.waitFor(5000);

    await tutorial.runPipeline(30000);
    console.log('Checking results for the first sleeper:');
    await tutorial.openNodeFiles(0);
    const outFiles = [
      "logs.zip",
      "out_1"
    ];
    await tutorial.checkResults(outFiles.length);

    await tutorial.waitFor(30000);
    console.log('Checking results for the last sleeper:');
    await tutorial.openNodeFiles(4);
    await tutorial.checkResults(outFiles.length);

    await tutorial.removeStudy();
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
