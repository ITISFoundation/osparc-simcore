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
  await tutorial.waitFor(30000);


  // open notebook
  await tutorial.openNode(1);

  const iframeHandles = tutorial.getIframe();
  console.log(iframeHandles);
  // expected two iframes = loading + raw-graph
  const frame = await iframeHandles[1].contentFrame();

  // inside the iFrame, click on the first notebook
  const notebookSelector = '#notebook_list > div:nth-child(2) > div > a';
  await frame.waitForSelector(notebookSelector);
  await frame.click(notebookSelector);
  await tutorial.waitFor(2000);
  await tutorial.takeScreenshot("openNotebook");

  // inside the first notebook, click Run button 4 times
  for (let i=0; i<4; i++) {
    const runBtnSelector = '#run_int > button:nth-child(1)';
    await frame.waitForSelector(runBtnSelector);
    await frame.click(runBtnSelector);
    await tutorial.waitFor(3000);
    await tutorial.takeScreenshot("pressRun_" + i+1);
  }


  await tutorial.retrieve();

  console.log('Checking results for the notebook:');
  await tutorial.openNodeFiles(1);
  const outFiles = [
    "notebooks.zip",
    "TheNumberNumber.txt"
  ];
  await tutorial.checkResults(outFiles.length);

  await tutorial.removeStudy();
  await tutorial.logOut();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
