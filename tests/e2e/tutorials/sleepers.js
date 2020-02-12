// node sleepers.js [url] [user] [password]

const utils = require('../utils/utils');

const tutorialBase = require('./tutorialBase');

const args = process.argv.slice(2);
if (args.length < 1) {
  
  process.exit(1);
}
const url = args[0];
const userPass = utils.getUserAndPass(args);
const user = userPass.user;
const pass = userPass.pass;
const newUser = userPass.newUser;

const templateName = "Sleepers";

async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(url, user, pass, newUser, templateName);

  tutorial.init();
  await tutorial.beforeScript();
  await tutorial.goTo();

  await tutorial.registerIfNeeded();
  await tutorial.login();
  await tutorial.openTemplate(1000);

  // Some time for loading the workbench
  await tutorial.waitFor(5000);

  await tutorial.runPipeline(25000);
  await tutorial.openFirstNodeFiles();
  await tutorial.checkResults();
  await tutorial.removeStudy();
  await tutorial.logOut();
  await tutorial.close();
}

runTutorial()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });