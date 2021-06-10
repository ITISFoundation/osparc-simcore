// node mattward.js [url] [user] [password] [--demo]

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

const templateName = "Mattward";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);
  let studyId
  try {
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][0]]);

    await tutorial.waitFor(30000, 'Wait for the output files to be pushed');

    // This study opens in fullscreen mode
    await tutorial.restoreIFrame();

    const outFiles = [
      "CAP_plot.csv",
      "CV_plot.csv",
      "Lpred_plot.csv",
      "V_pred_plot.csv",
      "input.csv",
      "t_plot.csv",
      "tst_plot.csv"
    ];

    await tutorial.openNodeFiles(0)
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
