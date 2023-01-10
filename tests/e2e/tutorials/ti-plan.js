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
  basicauthUsername,
  basicauthPassword,
  enableDemoMode
} = utils.parseCommandLineArguments(args)

const studyName = "TI Planning Tool";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, studyName, user, pass, newUser, basicauthUsername, basicauthPassword, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();

    await utils.sleep(2000, "Wait for Quick Start dialog");
    await tutorial.closeQuickStart();

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
    const esId = workbenchData["nodeIds"][0];
    const tiId = workbenchData["nodeIds"][2];
    const ppId = workbenchData["nodeIds"][3];

    // wait for the three services, except the optimizer
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [esId],
      startTimeout,
      false
    );

    // Make Electrode Selector selection
    await tutorial.takeScreenshot("electrodeSelector_before");
    const electrodeSelectorIframe = await tutorial.getIframe(esId);
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
    await tutorial.waitForStudyDone(studyId, 480000);
    await tutorial.takeScreenshot("optimizer_after");
    await tutorial.waitAndClick("preparingInputsCloseBtn");
    await tutorial.waitFor(2000, "Optimizer Finished");

    // Load Post Pro Analysis
    await tutorial.takeScreenshot("postpro_start");
    // wait for iframe to be ready, it might take a while in Voila
    const postProIframe = await tutorial.waitForVoilaIframe(tiId);
    // wait for iframe to be rendered
    await tutorial.waitForVoilaRendered(postProIframe);

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
    // Click on the "Export Report" button
    const buttonsExportReport = await utils.getButtonsWithText(postProIframe, "Export Report");
    await buttonsExportReport[0].click();
    await tutorial.waitFor(5000, "Export Report");
    await tutorial.takeScreenshot("postpro_export_report");

    const outFiles = [
      "output_1.zip",
      "TIP_report.pdf",
      "results.csv"
    ];
    await tutorial.checkNodeOutputsAppMode(tiId, outFiles, true);

    // Check s4l
    await tutorial.waitAndClick("AppMode_NextBtn");
    await tutorial.testS4LTIPostPro(ppId);
  }
  catch (err) {
    // if it fails because the optimizer times out, close the "Preparing Inputs" view first
    const page = tutorial.getPage();
    const id = '[osparc-test-id=preparingInputsCloseBtn]';
    await page.waitForSelector(id, {
      timeout: 1000
    })
      .then(() => page.click(id))
      .catch(() => console.log("Preparing Inputs window not found"));

    tutorial.setTutorialFailed(true, false);
    console.log('Tutorial error: ' + err);
    throw "Tutorial Failed";
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
