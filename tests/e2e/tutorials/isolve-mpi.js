// node isolve-mpi.js [url] [--user user] [--pass password] [--demo]

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

    await tutorial.checkNodeLogsFunctional();
  }
  catch (err) {
    await tutorial.setTutorialFailed(err);
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.leave(studyId);
  }

  if (tutorial.getTutorialFailed()) {
    throw tutorial.getTutorialFailedReason();
  }
}

runTutorial()
  .catch(error => {
    console.log(`[ERROR] Tutorial failed: '${error}'`);
    process.exit(1);
  });
