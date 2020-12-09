const { TutorialBase } = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');
const assert = require('assert');
const auto = require('../utils/auto');

const {
  user,
  pass,
} = utils.getUserAndPass();
console.log(user, pass)

const STUDY_NAME = 'study_tag_test';
const TAG_NAME = 'tag_tag_test';
const TAG_NAME_2 = 'tag_tag_test_2';
let studyId = null;
let tagId = null;

beforeAll(async() => {
  await page.goto(url);
}, ourTimeout);

describe('testing the tags', () => {
  test('test test', async () => {
    await auto.register(page, user, pass);
  }, ourTimeout);
});
async function run() {

  const baseActions = new TutorialBase(url, null, user, pass, null, enableDemoMode);
  const page = await baseActions.start();

  /**
   * This function records the IDs of the study and tag created in order to later remove them.
   */
  const responseHandler = response => {
    if (response.url().endsWith('/tags') && response.request().method() === 'POST') {
      response.json()
        .then(({ data: { id } }) => {
          console.log("Tag created, id", id);
          tagId = id;
        });
    }
    if (response.url().endsWith('/projects') && response.request().method() === 'POST') {
      response.json()
        .then(({ data: { uuid } }) => {
          console.log("Study created, uuid", uuid);
          studyId = uuid;
        });
    }
  }
  page.on('response', responseHandler);

  try {
    const waitAndClick = (selector, clickCount=1) => page.waitForSelector(selector)
      .then(el => el.click({ clickCount }));
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
    let tagFilterMenu = await page.waitForSelector('[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"])');
    assert((await tagFilterMenu.evaluate(el => el.innerText)).includes(TAG_NAME), "New tag is not present in filter");
    // Assign to study
    await waitAndClick('[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [osparc-test-id="studyItemMenuButton"]');
    await waitAndClick('[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"]) > div:nth-child(2)');
    await waitAndClick('[osparc-test-id="editStudyBtn"]');
    await waitAndClick('[osparc-test-id="editStudyEditTagsBtn"]');
    await waitAndClick('[qxclass="osparc.component.form.tag.TagToggleButton"]');
    await waitAndClick('[qxclass="osparc.component.form.tag.TagManager"] > .qx-workbench-small-cap-captionbar [qxclass="qx.ui.form.Button"]');
    // UI displays the change
    let displayedTag = await page.waitForSelector('[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [qxclass="osparc.ui.basic.Tag"]')
    assert((await displayedTag.evaluate(el => el.innerText)).includes(TAG_NAME), "Tag attachment is not reflected in UI");
    await waitAndClick('.qx-service-window[qxclass="osparc.ui.window.Window"] > .qx-workbench-small-cap-captionbar [qxclass="qx.ui.form.Button"]');
    // Change the tag
    await waitAndClick('[osparc-test-id="userMenuMainBtn"]');
    await waitAndClick('[osparc-test-id="userMenuPreferencesBtn"]');
    await waitAndClick('[osparc-test-id="preferencesTagsTabBtn"]');
    await waitAndClick('[qxclass="osparc.component.form.tag.TagItem"] [qxclass="qx.ui.form.Button"]');
    await waitAndClick('[qxclass="osparc.component.form.tag.TagItem"] input[type="text"]', 2);
    await page.keyboard.type(TAG_NAME_2);
    await waitAndClick('[qxclass="osparc.component.form.tag.TagItem"] [qxclass="osparc.ui.form.FetchButton"]');
    await waitAndClick('[osparc-test-id="preferencesWindowCloseBtn"]');
    // Check that tag name changed in filter and study list
    await waitAndClick('[qxclass="osparc.component.filter.UserTagsFilter"] [qxclass="qx.ui.toolbar.MenuButton"]');
    tagFilterMenu = await page.waitForSelector('[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"])');
    assert((await tagFilterMenu.evaluate(el => el.innerText)).includes(TAG_NAME_2), "New tag is not present in filter");
    displayedTag = await page.waitForSelector('[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [qxclass="osparc.ui.basic.Tag"]')
    assert((await displayedTag.evaluate(el => el.innerText)).includes(TAG_NAME_2), "Tag attachment is not reflected in UI");
  }
  finally {
    // Cleaning
    await page.evaluate(`
      Promise.all([
        osparc.data.Resources.fetch('studies', 'delete', { url: { projectId: '${studyId}' } }, '${studyId}'),
        osparc.data.Resources.fetch('tags', 'delete', { url: { tagId: '${tagId}' } }, '${tagId}')
      ]);
    `);
    await baseActions.close();
  }
}

let exitCode = 0;
// await run()
//   .catch(err => {
//     console.log('Tags e2e', err);
//     exitCode = 1;
//   })
//   .finally(() => {
//     process.exit(exitCode);
//   });
