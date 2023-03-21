// node login.js [url] [user] [password] [timeout] [--demo]

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

const serviceName = "login";

async function runLogin() {
  const tutorialRunner = new tutorialBase.TutorialBase(url, serviceName, user, pass, newUser, basicauthUsername, basicauthPassword, enableDemoMode);
  let studyId;
  try {
    await tutorialRunner.start();
  }
  catch (err) {
    await tutorialRunner.setTutorialFailed(true);
    console.log('login error: ' + err);
  }
  finally {
    await tutorialRunner.leave(studyId);
  }

  if (tutorialRunner.getTutorialFailed()) {
    throw "login Failed";
  }
}

runLogin()
  .catch(error => {
    console.log('Puppeteer error: ' + error);
    process.exit(1);
  });
