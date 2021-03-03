// node jupyters.js [url] [user] [password] [--demo]

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

const templateName = "Jupyters";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);

  let studyId = null;
  try {
    tutorial.startScreenshooter();
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];
    console.log("Study ID:", studyId);

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][1], workbenchData["nodeIds"][2]]);

    // open jupyterNB
    await tutorial.openNode(1);

    const iframeHandles = await tutorial.getIframe();
    const iframes = [];
    for (let i = 0; i < iframeHandles.length; i++) {
      const frame = await iframeHandles[i].contentFrame();
      iframes.push(frame);
    }
    const nbIframe = iframes.find(iframe => iframe._url.endsWith("tree?"));

    // inside the iFrame, open the first notebook
    const notebookCBSelector = '#notebook_list > div:nth-child(2) > div > input[type=checkbox]';
    await nbIframe.waitForSelector(notebookCBSelector);
    await nbIframe.click(notebookCBSelector);
    await tutorial.waitFor(2000);
    const notebookViewSelector = "#notebook_toolbar > div.col-sm-8.no-padding > div.dynamic-buttons > button.view-button.btn.btn-default.btn-xs"
    await nbIframe.waitForSelector(notebookViewSelector);
    await nbIframe.click(notebookViewSelector);
    await tutorial.waitFor(2000);
    await tutorial.takeScreenshot("openNotebook");

    // inside the first notebook, click Run all button
    const runAllButtonSelector = '#run_int > button:nth-child(4)';
    await utils.waitAndClick(nbIframe, runAllButtonSelector)
    // inside the first notebook, click confirm run all
    const confirmRunAllButtonSelector = 'body > div.modal.fade.in > div > div > div.modal-footer > button.btn.btn-default.btn-sm.btn-danger';
    await utils.waitAndClick(nbIframe, confirmRunAllButtonSelector)
    // now check that the input contains [4]
    const finishedRunningCheckboxSelector = '#notebook-container > div:nth-child(5) > div.input > div.prompt_container > div.prompt.input_prompt';
    await nbIframe.waitForSelector(finishedRunningCheckboxSelector);


    let inputElement = await nbIframe.$(finishedRunningCheckboxSelector);



    // async function checkNotebookCompleted(page, el) {
    //   let value = await page.evaluate(el => el.textContent, el);
    //   return value.match(/\[[0-9]+\]/) != null;
    // }
    await nbIframe.waitForFunction(async (page, el) => {
      let value = await page.evaluate(el => el.textContent, el);
      if (value.match(/\[[0-9]+\]/)) {
        return true;
      } else {
        return false;
      }
    }, {}, nbIframe, inputElement);
    // await nbIframe.waitForFunction(async (page, selector) => {
    //   element = await page.$(selector);
    //   return element.innerText.match(/\[[0-9]+\]/) != null;
    // }, { polling: 200, timeout: 20000 }, nbIframe, finishedRunningCheckboxSelector);
    // checkNotebookCompleted(nbIframe, inputElement, /\[[0-9]+\]/g), { polling: 200, timeout: 20000 });



    console.log('Checking results for the notebook:');
    await tutorial.openNodeFiles(1);
    const outFiles = [
      "TheNumberNumber.txt",
      "notebooks.zip"
    ];
    await tutorial.checkResults(outFiles.length);


    // open jupyter lab
    await tutorial.openNode(2);

    const iframeHandles2 = await tutorial.getIframe();
    const iframes2 = [];
    for (let i = 0; i < iframeHandles2.length; i++) {
      const frame = await iframeHandles2[i].contentFrame();
      iframes2.push(frame);
    }
    const jLabIframe = iframes2.find(iframe => iframe._url.endsWith("lab?"));

    // inside the iFrame, open the first notebook
    const input2outputFileSelector = '#filebrowser > div.lm-Widget.p-Widget.jp-DirListing.jp-FileBrowser-listing.jp-DirListing-narrow > ul > li:nth-child(3)';
    await jLabIframe.waitForSelector(input2outputFileSelector);
    await jLabIframe.click(input2outputFileSelector, {
      clickCount: 2
    });
    await tutorial.waitFor(2000);

    // click Run Menu
    const mainRunMenuBtnSelector = '#jp-MainMenu > ul > li:nth-child(4)';
    await jLabIframe.waitForSelector(mainRunMenuBtnSelector);
    await jLabIframe.click(mainRunMenuBtnSelector);
    await tutorial.waitFor(1000);

    // click Run All Cells
    const mainRunAllBtnSelector = '  body > div.lm-Widget.p-Widget.lm-Menu.p-Menu.lm-MenuBar-menu.p-MenuBar-menu > ul > li:nth-child(17)';
    await jLabIframe.waitForSelector(mainRunAllBtnSelector);
    await jLabIframe.click(mainRunAllBtnSelector);
    await tutorial.waitFor(6000);
    await tutorial.takeScreenshot("pressRunJLab");

    console.log('Checking results for the jupyter lab:');
    await tutorial.openNodeFiles(2);
    const outFiles2 = [
      "work.zip",
      "TheNumber.txt"
    ];
    await tutorial.checkResults(outFiles2.length);
  }
  catch (err) {
    tutorial.setTutorialFailed(true);
    console.log('Tutorial error: ' + err);
  }
  finally {
    // delete study if succesfull or puppeteer_XX
    if (!tutorial.getTutorialFailed() || (user.includes("puppeteer_") && studyId)) {
      await tutorial.toDashboard();
      await tutorial.removeStudy(studyId);
    }

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
