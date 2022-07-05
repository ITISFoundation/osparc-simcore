// node jupyters.js [url] [user] [password] [--demo]

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

const serviceName = "JupyterLab sim4life";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, serviceName, user, pass, newUser, enableDemoMode);
  let studyId
  try {
    await tutorial.start();
    const studyData = await tutorial.openService(1000);
    studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    console.log(workbenchData);
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [workbenchData["nodeIds"][0]],
      startTimeout,
      false
    );
    console.log("HEY MAN I AM HERE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");

    // open JLab
    // await tutorial.openNode(0);
    await tutorial.takeScreenshot("opened " + serviceName);

    // get the file menu
    await utils.waitAndClick(jLabIframe, '#jp-MainMenu > ul > li:nth-child(1)', timeout = 10000);
    await tutorial.takeScreenshot("opened_File_menu");
    // click the New entry
    await utils.waitAndClick(jLabIframe, "#jp-mainmenu-file > ul > li:nth-child(1) > div.lm-Menu-itemLabel.p-Menu-itemLabel");
    await tutorial.takeScreenshot("opened_File_New_entry");
    // click the Terminal entry
    await utils.waitAndClick(jLabIframe, "#jp-mainmenu-file-new > ul > li:nth-child(3) > div.lm-Menu-itemLabel.p-Menu-itemLabel")
    await tutorial.takeScreenshot("created_File_New_Terminal_entry");
    await tutorial.waitFor(3000, "wait for terminal to start...");
    await tutorial.takeScreenshot("terminal is up");
  }
  catch (err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    await tutorial.toDashboard()
    await tutorial.removeStudy(studyId, 20000);
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
