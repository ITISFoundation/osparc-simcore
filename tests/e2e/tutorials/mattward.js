// node mattward.js [url] [user] [password]

const utils = require('../utils/utils');

const tutorialBase = require('./tutorialBase');

const args = process.argv.slice(2);
if (args.length < 1) {
  
  process.exit(1);
}
const url = args[0];
const {
  user,
  pass,
  newUser
} = utils.getUserAndPass(args);
const templateName = "Mattward";

async function runTutorial () {
  const tutorial = new tutorialBase.TutorialBase(url, user, pass, newUser, templateName);

  tutorial.init();
  await tutorial.beforeScript();
  await tutorial.goTo();

  await tutorial.registerIfNeeded();
  await tutorial.login();
  await tutorial.openTemplate(1000);

  // Wait service to start and output files to be pushed
  await tutorial.waitFor(60000);

  await tutorial.openNodeFiles(0);
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