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

const templateName = "JupyterLabs";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);
  let studyId
  try {
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    await tutorial.waitForServices(
      workbenchData["studyId"],
      [workbenchData["nodeIds"][1], workbenchData["nodeIds"][2]],
      startTimeout,
      false
    );

    await tutorial.waitFor(2000);

    for (let j = 1; j < 3; j++) {
      // open jupyterNB
      await tutorial.openNode(j);
      await tutorial.waitFor(35000);


      // Run the jlab nbook
      let iframeHandles2 = await tutorial.getIframe();
      let iframes2 = [];
      for (let i = 0; i < iframeHandles2.length; i++) {
        const frame = await iframeHandles2[i].contentFrame();
        iframes2.push(frame);
      }
      let jLabIframe = iframes2.find(iframe => iframe._url.includes(workbenchData["nodeIds"][j]));

      let input2outputFileSelector = '[title~="jl_notebook.ipynb"]';
      await jLabIframe.waitForSelector(input2outputFileSelector);
      await jLabIframe.click(input2outputFileSelector, {
        clickCount: 2
      });
      await tutorial.waitFor(5000);
      // click Run Menu
      let mainRunMenuBtnSelector = '#jp-MainMenu > ul > li:nth-child(4)'; // select the Run Menu
      await utils.waitAndClick(jLabIframe, mainRunMenuBtnSelector)

      // click Run All Cells
      let mainRunAllBtnSelector = '#jp-mainmenu-run > ul > li:nth-child(12)'; // select the Run
      await utils.waitAndClick(jLabIframe, mainRunAllBtnSelector)

      if (j === 2) {
        await tutorial.waitFor(40000); // we are solving an em problem
      }


      const outFiles = [
        "TheNumber.txt",
        "workspace.zip"
      ];
      await tutorial.checkNodeOutputs(j, outFiles, true, false);
    }
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
