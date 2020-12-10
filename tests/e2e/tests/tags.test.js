const { TutorialBase } = require('../tutorials/tutorialBase');
const utils = require('../utils/utils');
const auto = require('../utils/auto');
const waitAndClick = require('../utils/utils').waitAndClick;

const {
  user,
  pass,
} = utils.getUserAndPass();

const STUDY_NAME = 'study_tag_test';
const TAG_NAME = 'tag_tag_test';
const TAG_NAME_2 = 'tag_tag_test_2';
let studyId = null;
let tagId = null;

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

beforeAll(async () => {
  page.on('response', responseHandler);
  await page.goto(url);
  await auto.register(page, user, pass);
  // Create new study
  await waitAndClick(page, '[osparc-test-id="newStudyBtn"]');
  // Edit its title and go back to dashboard
  await waitAndClick(page, '[qxclass="osparc.desktop.NavigationBar"] [qxclass="osparc.ui.form.EditLabel"]');
  await page.keyboard.type(STUDY_NAME);
  await page.keyboard.press('Enter');
  await page.waitForFunction(studyName => {
    return document.querySelector(
      '[qxclass="osparc.desktop.NavigationBar"] [qxclass="osparc.ui.form.EditLabel"] [qxclass="qx.ui.basic.Label"]'
    ).innerText === studyName;
  }, {}, STUDY_NAME);
  await waitAndClick(page, '[osparc-test-id="dashboardBtn"]');
}, ourTimeout * 2);

afterAll(async () => {
  // Cleaning
  await page.evaluate(`
    Promise.all([
      osparc.data.Resources.fetch('studies', 'delete', { url: { projectId: '${studyId}' } }, '${studyId}'),
      osparc.data.Resources.fetch('tags', 'delete', { url: { tagId: '${tagId}' } }, '${tagId}')
    ]);
  `);
  page.off('response', responseHandler);
  await auto.logOut(page);
}, ourTimeout);

test('add a tag', async () => {
  // Add a tag
  await waitAndClick(page, '[osparc-test-id="userMenuMainBtn"]');
  await waitAndClick(page, '[osparc-test-id="userMenuPreferencesBtn"]');
  await waitAndClick(page, '[osparc-test-id="preferencesTagsTabBtn"]');
  await waitAndClick(page, '[osparc-test-id="addTagBtn"]');
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagItem"]:last-of-type input[type="text"]');
  await page.keyboard.type(TAG_NAME);
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagItem"]:last-of-type [qxclass="osparc.ui.form.FetchButton"]');
  // Check tag was added
  await page.waitForFunction(tagName => {
    const el = document.querySelector(
      '[qxclass="osparc.component.form.tag.TagItem"]:last-of-type [qxclass="osparc.ui.basic.Tag"]'
    );
    return el && el.innerText === tagName;
  }, {}, TAG_NAME);
  // Close properties
  await waitAndClick(page, '[osparc-test-id="preferencesWindowCloseBtn"]');
}, ourTimeout);

test('tag shows in filters', async () => {
  // Check that tag shows in filter
  await waitAndClick(page, '[qxclass="osparc.component.filter.UserTagsFilter"] [qxclass="qx.ui.toolbar.MenuButton"]');
  let tagFilterMenu = await page.waitForSelector('[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"])');
  expect(await tagFilterMenu.evaluate(el => el.innerText)).toContain(TAG_NAME);
}, ourTimeout);

test('assign tag and reflect changes', async () => {
  await page.waitForSelector(
    '[qxclass="osparc.dashboard.StudyBrowserButtonItem"] > [qxclass="osparc.component.widget.Thumbnail"]',
    { hidden: true }
  );
  // Assign to study
  await waitAndClick(page, '[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [osparc-test-id="studyItemMenuButton"]');
  await waitAndClick(page, '[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"]) > div:nth-child(2)');
  await waitAndClick(page, '[osparc-test-id="editStudyBtn"]');
  await waitAndClick(page, '[osparc-test-id="editStudyEditTagsBtn"]');
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagToggleButton"]');
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagManager"] > .qx-workbench-small-cap-captionbar [qxclass="qx.ui.form.Button"]');
  // UI displays the change
  let displayedTag = await page.waitForSelector('[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [qxclass="osparc.ui.basic.Tag"]')
  await waitAndClick(page, '.qx-service-window[qxclass="osparc.ui.window.Window"] > .qx-workbench-small-cap-captionbar [qxclass="qx.ui.form.Button"]');
  expect(await displayedTag.evaluate(el => el.innerText)).toContain(TAG_NAME);
}, ourTimeout);

test('change tag and reflect changes', async () => {
  // Change the tag
  await waitAndClick(page, '[osparc-test-id="userMenuMainBtn"]');
  await waitAndClick(page, '[osparc-test-id="userMenuPreferencesBtn"]');
  await waitAndClick(page, '[osparc-test-id="preferencesTagsTabBtn"]');
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagItem"] [qxclass="qx.ui.form.Button"]');
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagItem"] input[type="text"]', 2);
  await page.keyboard.type(TAG_NAME_2);
  await waitAndClick(page, '[qxclass="osparc.component.form.tag.TagItem"] [qxclass="osparc.ui.form.FetchButton"]');
  await page.waitForFunction(tagName => {
    const el = document.querySelector(
      '[qxclass="osparc.component.form.tag.TagItem"] [qxclass="osparc.ui.basic.Tag"]'
    );
    return el && el.innerText === tagName;
  }, {}, TAG_NAME_2);
  // Close properties
  await waitAndClick(page, '[osparc-test-id="preferencesWindowCloseBtn"]');
  // Check that tag name changed in filter and study list
  await waitAndClick(page, '[qxclass="osparc.component.filter.UserTagsFilter"] [qxclass="qx.ui.toolbar.MenuButton"]');
  tagFilterMenu = await page.waitForSelector('[qxclass="qx.ui.menu.Menu"]:not([style*="display: none"])');
  expect(await tagFilterMenu.evaluate(el => el.innerText)).toContain(TAG_NAME_2);
  await page.waitForFunction(tagName => {
    const el = document.querySelector(
      '[qxclass="osparc.dashboard.StudyBrowserButtonItem"] [qxclass="osparc.ui.basic.Tag"]'
    );
    return el && el.innerText === tagName;
  }, {}, TAG_NAME_2);
}, ourTimeout);
