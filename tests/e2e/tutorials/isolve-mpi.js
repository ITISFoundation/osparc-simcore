// node isolve-mpi.js [url] [user] [password] [--demo]

const utils = require('../utils/utils');
const tutorialBase = require('./tutorialBase');

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

const templateName = "isolve-mpi";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, basicauthUsername, basicauthPassword, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];

    await tutorial.waitFor(5000, 'Some time for loading the workbench');

    await tutorial.runPipeline();
    await tutorial.waitForStudyDone(studyId, startTimeout);

    const outFiles = [
      "logs.zip",
      "output.h5",
      "log.tgz"
    ];
    await tutorial.checkNodeOutputs(1, outFiles);

    // check logs
    const mustHave = "Running MPI version 3.1 on 2 processes";
    const found = await tutorial.findLogMessage(mustHave);
    if (found) {
      console.log("Running MPI version 3.1 on 2 processes");
    }
    else {
      throw "MPI not working";
    }
  }
  catch(err) {
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

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
