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

const templateName = "Jupyters";

async function runTutorial() {
  const tutorial = new tutorialBase.TutorialBase(url, templateName, user, pass, newUser, enableDemoMode);
  let studyId
  try {
    await tutorial.start();
    const studyData = await tutorial.openTemplate(1000);
    studyId = studyData["data"]["uuid"];

    const workbenchData = utils.extractWorkbenchData(studyData["data"]);
    await tutorial.waitForServices(workbenchData["studyId"], [workbenchData["nodeIds"][1], workbenchData["nodeIds"][2]], startTimeout);
    await tutorial.waitFor(2000);

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
    await utils.waitAndClick(nbIframe, notebookCBSelector);
    const notebookViewSelector = "#notebook_toolbar > div.col-sm-8.no-padding > div.dynamic-buttons > button.view-button.btn.btn-default.btn-xs"
    await utils.waitAndClick(nbIframe, notebookViewSelector);
    console.log("notebook iframe found");
    await tutorial.waitFor(5000);

    // inside the first notebook, click Run all button
    const cellMenuSelector = '#menus > div > div > ul > li:nth-child(5) > a'
    await utils.waitAndClick(nbIframe, cellMenuSelector);
    const runAllCellsSelector = '#run_all_cells > a'
    await utils.waitAndClick(nbIframe, runAllCellsSelector);
    await tutorial.takeScreenshot("pressRunAllButtonNotebook");

    // now check that the input contains [4]
    console.log('Waiting for notebook results...');
    const finishedRunningCheckboxSelector = '#notebook-container > div:nth-child(5) > div.input > div.prompt_container > div.prompt.input_prompt';
    // the page scrolls down, so first wait so that it becomes visible
    await nbIframe.waitForSelector(finishedRunningCheckboxSelector);
    await nbIframe.waitForFunction('document.querySelector("' + finishedRunningCheckboxSelector + '").innerText.match(/\[[0-9]+\]/)');
    await tutorial.takeScreenshot("notebookWaitingForNotebookCompleted");
    console.log('...waiting completed');
    const element = await nbIframe.$(finishedRunningCheckboxSelector);
    const value = await nbIframe.evaluate(el => el.textContent, element);
    console.log('Results for the notebook cell is:', value);
    // NOTE: we need to wait here to get the results.
    await tutorial.waitFor(15000, 'we need to wait here to get the results');

    const outFiles = [
      "TheNumberNumber.txt",
      "notebooks.zip"
    ];
    await tutorial.checkNodeOutputs(1, outFiles);


    // open jupyter lab
    await tutorial.openNode(2);

    const iframeHandles2 = await tutorial.getIframe();
    const iframes2 = [];
    for (let i = 0; i < iframeHandles2.length; i++) {
      const frame = await iframeHandles2[i].contentFrame();
      iframes2.push(frame);
    }
    const jLabIframe = iframes2.find(iframe => iframe._url.includes("/lab"));
    await utils.runAllCellsInJupyterLab(tutorial.getPage(), jLabIframe, "input2output.ipynb");

    console.log('Waiting for jupyter lab results...');
    const labCompletedInputSelector = 'div.lm-Widget.p-Widget.jp-MainAreaWidget.jp-NotebookPanel.jp-Document.jp-Activity > div:nth-child(2) > div:nth-child(3) > div.lm-Widget.p-Widget.lm-Panel.p-Panel.jp-Cell-inputWrapper > div.lm-Widget.p-Widget.jp-InputArea.jp-Cell-inputArea > div.lm-Widget.p-Widget.jp-InputPrompt.jp-InputArea-prompt';
    await jLabIframe.waitForFunction('document.querySelector("' + labCompletedInputSelector + '").innerText.match(/\[[0-9]+\]/)');
    const jLabElement = await jLabIframe.$(labCompletedInputSelector);
    const jLabVvalue = await jLabIframe.evaluate(el => el.textContent, jLabElement);
    console.log('Checking results for the jupyter lab cell:', jLabVvalue);

    await tutorial.waitFor(15000, 'wait sufficiently before getting the results');

    console.log('Checking results for the jupyter lab:');
    const outFiles2 = [
      "work.zip",
      "TheNumber.txt"
    ];
    await tutorial.checkNodeOutputs(2, outFiles2);
  }
  catch (err) {
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
