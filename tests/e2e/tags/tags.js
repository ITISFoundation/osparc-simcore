const { TutorialBase } = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  enableDemoMode
} = utils.parseCommandLineArguments(args);

const STUDY_NAME = 'tag_test'

async function run() {
  const baseActions = new TutorialBase(url, null, user, pass, null, enableDemoMode);
  const page = await baseActions.start();
  const waitAndClick = selector => page.waitForSelector(selector).then(el => el.click())
  // Create new study
  await waitAndClick('[osparc-test-id="newStudyBtn"]');
  // Edit its title and go back to dashboard
  await waitAndClick('[qxclass="osparc.desktop.NavigationBar"] [qxclass="osparc.ui.form.EditLabel"]');
  await page.keyboard.type(STUDY_NAME);
  await page.keyboard.press('Enter');
  await page.waitForFunction(
    'document.querySelector(\'' +
      '[qxclass="osparc.desktop.NavigationBar"] [qxclass="osparc.ui.form.EditLabel"] [qxclass="qx.ui.basic.Label"]' +
    `').innerText === '${STUDY_NAME}'`
  );
  await waitAndClick('[osparc-test-id="dashboardBtn"]');
  // Add a tag
  await waitAndClick('[osparc-test-id="userMenuMainBtn"]');
  await waitAndClick('[osparc-test-id="userMenuPreferencesBtn"]');
  await waitAndClick('[osparc-test-id="preferencesTagsTabBtn"]');
  await waitAndClick('[osparc-test-id="addTagBtn"]');
  await baseActions.close();
}

run()
  .catch(err => {
    console.log('Tags e2e', err);
    process.exit(1);
  });
