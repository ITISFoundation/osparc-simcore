const { TutorialBase } = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  enableDemoMode
} = utils.parseCommandLineArguments(args);

(async function() {

  const baseActions = new TutorialBase(url, null, user, pass, null, enableDemoMode);

  await baseActions.start();

})();
