// node rclone_large.js [url] [--user user] [--pass password] [--demo]

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

const templateName = "rclone -- large";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, basicauthUsername, basicauthPassword, enableDemoMode);
  let studyId;
  try {
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [workbenchData["nodeIds"][0], workbenchData["nodeIds"][1], workbenchData["nodeIds"][2], workbenchData["nodeIds"][3], workbenchData["nodeIds"][4]],
      startTimeout,
      false
    );

    await tutorial.waitFor(5000);

    for (let j = 0; j < 5; j++) {
      // open JLab
      await tutorial.openNode(j);
      await tutorial.waitFor(12000);

      // Run the jlab nbook
      const jLabIframe = await tutorial.getIframe(workbenchData["nodeIds"][j]);

      await tutorial.takeScreenshot("before_nb_selection");
      const input2outputFileSelector = '[title~="TouchRandomFileLarge.ipynb"]';
      await jLabIframe.waitForSelector(input2outputFileSelector);
      await jLabIframe.click(input2outputFileSelector, {
        clickCount: 2
      });
      await tutorial.takeScreenshot("after_nb_selection");

      await tutorial.waitFor(5000);
      // click Run Menu
      const mainRunMenuBtnSelector = '#jp-MainMenu > ul > li:nth-child(4)'; // select the Run Menu
      await utils.waitAndClick(jLabIframe, mainRunMenuBtnSelector)

      await tutorial.takeScreenshot("after_run_menu");

      // click Run All Cells
      const mainRunAllBtnSelector = '#jp-mainmenu-run > ul > li:nth-child(12)'; // select the Run
      await utils.waitAndClick(jLabIframe, mainRunAllBtnSelector)

      await tutorial.takeScreenshot("after_run_all_menu");


      await tutorial.waitFor(60000); // we are creating 12 x 1 GB files with 75 % probability
    }
  }
  catch (err) {
    await tutorial.setTutorialFailed();
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
