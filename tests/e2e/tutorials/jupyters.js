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
  const tutorial = new tutorialBase.TutorialBase(url, user, pass, newUser, templateName, enableDemoMode);

  tutorial.init();
  await tutorial.beforeScript();
  await tutorial.goTo();

  const needsRegister = await tutorial.registerIfNeeded();
  if (!needsRegister) {
    await tutorial.login();
  }
  await tutorial.openTemplate(5000);

  // Some time for loading notebook and jupyter lab
  await tutorial.waitFor(25000);


  // open notebook
  await tutorial.openNode(1);

  const iframeHandles = await tutorial.getIframe();
  // expected two iframes = loading + jupyterNB
  const nbIframe = await iframeHandles[1].contentFrame();

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

  // inside the first notebook, click Run button 4 times
  const runNBBtnSelector = '#run_int > button:nth-child(1)';
  const runNotebookTimes = 4;
  for (let i=0; i<runNotebookTimes; i++) {
    await nbIframe.waitForSelector(runNBBtnSelector);
    await nbIframe.click(runNBBtnSelector);
    await tutorial.waitFor(3000);
    await tutorial.takeScreenshot("pressRunNB_" + i+1);
  }

  await tutorial.retrieve();

  console.log('Checking results for the notebook:');
  await tutorial.openNodeFiles(1);
  const outFiles = [
    "notebooks.zip",
    "TheNumberNumber.txt"
  ];
  await tutorial.checkResults(outFiles.length);


  // open jupyter lab
  await tutorial.openNode(2);

  await tutorial.retrieve();

  const iframeHandles2 = await tutorial.getIframe();
  // expected three iframes = loading + jupyterNB + jupyterLab
  const jLabIframe = await iframeHandles2[2].contentFrame();

  // inside the iFrame, open the first notebook
  const workFolderSelector = '#filebrowser > div.lm-Widget.p-Widget.jp-DirListing.jp-FileBrowser-listing.jp-DirListing-narrow > ul > li:nth-child(3)';
  await jLabIframe.waitForSelector(workFolderSelector);
  await jLabIframe.click(workFolderSelector, {
    clickCount: 2
  });
  await tutorial.waitFor(2000);

  const input2outputFileSelector = '#filebrowser > div.lm-Widget.p-Widget.jp-DirListing.jp-FileBrowser-listing.jp-DirListing-narrow > ul > li:nth-child(1)';
  await jLabIframe.waitForSelector(input2outputFileSelector);
  await jLabIframe.click(input2outputFileSelector, {
    clickCount: 2
  });
  await tutorial.waitFor(2000);

  // click Run Menu
  const mainRunMenuBtnSelector = '#jp-MainMenu > ul > li:nth-child(4)';
  await nbIframe.waitForSelector(mainRunMenuBtnSelector);
  await nbIframe.click(mainRunMenuBtnSelector);
  await tutorial.waitFor(2000);

  // click Run All Cells
  const mainRunAllBtnSelector = 'body > div.lm-Widget.p-Widget.lm-Menu.p-Menu.lm-MenuBar-menu.p-MenuBar-menu > ul > li:nth-child(17)';
  await nbIframe.waitForSelector(mainRunAllBtnSelector);
  await nbIframe.click(mainRunAllBtnSelector);
  await tutorial.waitFor(6000);
  await tutorial.takeScreenshot("pressRunJLab");


  await tutorial.removeStudy();
  await tutorial.logOut();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
