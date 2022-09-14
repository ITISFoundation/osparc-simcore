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
    await tutorial.takeScreenshot("electrodeSelector_before");
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
    await tutorial.waitFor(5000, "Finish Electrode Selector SetUp");
    await tutorial.takeScreenshot("electrodeSelector_after");

    // Run optimizer
    await tutorial.waitAndClick("AppMode_NextBtn");
    await tutorial.waitFor(5000, "Running Optimizer");
    await tutorial.takeScreenshot("optimizer_before");
    // one permutation should take less than 180"
    await tutorial.waitForStudyDone(studyId, 240000);
    await tutorial.takeScreenshot("optimizer_after");
    await tutorial.waitAndClick("preparingInputsCloseBtn");
    await tutorial.waitFor(5000, "Optimizer Finished");

    // Load Post Pro Analysis
    await tutorial.takeScreenshot("postpro_start");
    const postProIframe = await tutorial.getIframe(workbenchData["nodeIds"][2]);
    // Click "Load Analysis" button
    const buttonsLoadAnalysis = await utils.getButtonsWithText(postProIframe, "Load Analysis");
    await buttonsLoadAnalysis[0].click();
    await tutorial.waitFor(10000, "Loading anaylsis");
    await tutorial.takeScreenshot("postpro_load_analysis");
    // Click on the first "Load" button
    const buttonsLoad = await utils.getButtonsWithText(postProIframe, "Load");
    await buttonsLoad[1].click();
    await tutorial.waitFor(30000, "Loading Fields");
    await tutorial.takeScreenshot("postpro_load_field");
    // Click on the "Add to Report" buttons
    const buttonsAddToReport = await utils.getButtonsWithText(postProIframe, "Add to Report");
    await buttonsAddToReport[0].click();
    await buttonsAddToReport[1].click();
    await tutorial.waitFor(5000, "Adding to Report");
    await tutorial.takeScreenshot("postpro_add_to_report");
    // Click on the "Export to S4L" buttons
    const buttonsExportToS4L = await utils.getButtonsWithText(postProIframe, "Export to S4L");
    await buttonsExportToS4L[0].click();
    await tutorial.waitFor(5000, "Export to S4L");
    await tutorial.takeScreenshot("postpro_export_to_s4l");
    // Click on the "Export to S4L" buttons
    const buttonsExportReport = await utils.getButtonsWithText(postProIframe, "Export Report");
    await buttonsExportReport[0].click();
    await tutorial.waitFor(5000, "Export to S4L");
    await tutorial.takeScreenshot("postpro_export_to_s4l");

    const outFiles = [
      "temp_ti_field.cache",
      "TIP_report.pdf",
      "table.csv"
    ];
    await tutorial.checkNodeOutputsAppMode(workbenchData["nodeIds"][2], outFiles, true, false);

    // Check s4l
    await tutorial.waitAndClick("AppMode_NextBtn");
    await tutorial.waitFor(5000, "Starting s4l");
    await tutorial.takeScreenshot("s4l");
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
