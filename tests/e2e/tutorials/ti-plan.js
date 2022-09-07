// node ti-plan.js [url] [user] [password] [timeout] [--demo]

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

const studyName = "TI Planning Tool";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, studyName, user, pass, newUser, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();

    await utils.sleep(2000, "Wait for Quick Start dialog");
    await tutorial.closeQuickStart();

    // check that the "New Study" is "New Plan"
    await tutorial.checkFirstStudyId("newPlanButton");

    // create New Plan
    const studyData = await tutorial.startNewPlan();
    studyId = studyData["data"]["uuid"];

    // check the app mode steps
    const appModeSteps = await tutorial.getAppModeSteps();
    if (appModeSteps.length !== 3) {
      throw "Three steps expected, got " + appModeSteps;
    }

    // wait for the three services
    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log(workbenchData);

    // wait for the three services, except the optimizer
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [workbenchData["nodeIds"][0], workbenchData["nodeIds"][2], workbenchData["nodeIds"][3]],
      startTimeout,
      false
    );

    // Make Electrode Selector selection
    const electrodeSelectorIframe = await tutorial.getIframe(workbenchData["nodeIds"][0]);
    await utils.waitAndClick(electrodeSelectorIframe, '[osparc-test-id="TargetStructure_Selector"]');
    await utils.waitAndClick(electrodeSelectorIframe, '[osparc-test-id="TargetStructure_Target_Hypothalamus"]');
    const selection = [
      ["E1+", "FT9"],
      ["E1-", "FT7"],
      ["E2+", "T9"],
      ["E2-", "T7"],
    ];
    for (let i = 0; i < selection.length; i++) {
      const grp = selection[i];
      await utils.waitAndClick(electrodeSelectorIframe, `[osparc-test-id="ElectrodeGroup_${grp[0]}_Start"]`);
      await utils.waitAndClick(electrodeSelectorIframe, `[osparc-test-id="Electrode_${grp[1]}"]`);
    }
    await utils.waitAndClick(electrodeSelectorIframe, `[osparc-test-id="FinishSetUp"]`);

    // Run optimizer
    await tutorial.waitAndClick("AppMode_NextBtn");
    await tutorial.waitFor(5000, "Running Optimizer");
    await tutorial.waitForStudyDone(studyId, 120000);
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
