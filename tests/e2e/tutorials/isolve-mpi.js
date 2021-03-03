// node isolve-mpi.js [url] [user] [password] [--demo]

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

const templateName = "isolve-mpi";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);

  try {
    tutorial.startScreenshooter();
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    const studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    // Some time for loading the workbench
    await tutorial.waitFor(5000);

    await tutorial.runPipeline();
    await tutorial.waitForStudyDone(studyId, 80000);

    await tutorial.openNodeFiles(1);
    const outFiles = [
      "logs.zip",
      "output.h5",
      "log.tgz"
    ];
    await tutorial.checkResults(outFiles.length);

    // check logs
    const mustHave = "Running MPI version 3.1 on 2 processes";
    const found = await tutorial.findLogMessage(mustHave);
    if (found) {
      console.log("Running MPI version 3.1 on 2 processes");
    }
    else {
      throw "MPI not working";
    }

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
