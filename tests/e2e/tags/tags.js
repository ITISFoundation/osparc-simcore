const { TutorialBase } = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');
const assert = require('assert');

const args = process.argv.slice(2);
const {
  url,
  user,
  pass,
  enableDemoMode
} = utils.parseCommandLineArguments(args);

const STUDY_NAME = 'study_tag_test'
const TAG_NAME = 'tag_tag_test'

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
  await page.waitForFunction(studyName => {
    return document.querySelector(
      '[qxclass="osparc.desktop.NavigationBar"] [qxclass="osparc.ui.form.EditLabel"] [qxclass="qx.ui.basic.Label"]'
    ).innerText === studyName;
  }, {}, STUDY_NAME);
  await waitAndClick('[osparc-test-id="dashboardBtn"]');
  // Add a tag
  await waitAndClick('[osparc-test-id="userMenuMainBtn"]');
  await waitAndClick('[osparc-test-id="userMenuPreferencesBtn"]');
  await waitAndClick('[osparc-test-id="preferencesTagsTabBtn"]');
  await waitAndClick('[osparc-test-id="addTagBtn"]');
  await waitAndClick('[qxclass="osparc.component.form.tag.TagItem"]:last-of-type input[type="text"]');
  await page.keyboard.type(TAG_NAME);
  await waitAndClick('[qxclass="osparc.component.form.tag.TagItem"]:last-of-type [qxclass="osparc.ui.form.FetchButton"]');
  // Check tag was added
  await page.waitForFunction(tagName => {
    const el = document.querySelector(
      '[qxclass="osparc.component.form.tag.TagItem"]:last-of-type [qxclass="osparc.ui.basic.Tag"]'
    );
    return el && el.innerText === tagName;
  }, {}, TAG_NAME);
  // Close properties
  await waitAndClick('[osparc-test-id="preferencesWindowCloseBtn"]');
  // Check that tag shows in filter
  await waitAndClick('[qxclass="osparc.component.filter.UserTagsFilter"] [qxclass="qx.ui.toolbar.MenuButton"]');
  const tagFilterMenu = await page.waitForSelector('[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"])');
  assert((await tagFilterMenu.evaluate(el => el.innerText)).includes(TAG_NAME), "New tag is not present in filter");
  // Assign to study
  await waitAndClick('[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [osparc-test-id="studyItemMenuButton"]');
  await waitAndClick('[osparc-test-id="studyItemMenuMoreInfo"]');
  await baseActions.close();
}

run()
  .catch(err => {
    console.log('Tags e2e', err);
    process.exit(1);
  });
