// OM rename this file and fix the test

const utils = require('../utils/utils');
const auto = require('../utils/auto');
const waitAndClick = require('../utils/utils').waitAndClick;

describe('tags testing', () => {
  const {
    user,
    pass,
  } = utils.getUserAndPass();

  const TAG_NAME = 'tag_test';
  const TAG_NAME_2 = 'tag_test_2';
  let studyId = null;
  let tagId = null;

  /**
   * This function records the IDs of the study and tag created in order to later remove them.
   */
  const responseHandler = response => {
    if (response.url().endsWith('/tags') && response.request().method() === 'POST') {
      response.json()
        .then(({
          data: {
            id
          }
        }) => {
          console.log("Tag created, id", id);
          tagId = id;
        });
    }
    if (response.url().endsWith('/projects') && response.request().method() === 'POST') {
      response.json()
        .then(({
          data: {
            uuid
          }
        }) => {
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
    // Wait until project is created and Dashboard button is enabled
    await utils.sleep(4000);
    await auto.toDashboard(page);
  }, ourTimeout * 2);

  afterAll(async () => {
    // Cleaning
    await page.evaluate(async function(studyId, tagId) {
      await osparc.data.Resources.fetch('studies', 'delete', {
        url: {
          "studyId": studyId
        }
      }, studyId);
      await osparc.data.Resources.fetch('tags', 'delete', {
        url: {
          tagId: tagId
        }
      }, tagId);
    }, studyId, tagId);
    page.off('response', responseHandler);
    await auto.logOut(page);
  }, ourTimeout);

  test('add a tag', async () => {
    // Add a tag
    await waitAndClick(page, '[osparc-test-id="userMenuBtn"]');
    await waitAndClick(page, '[osparc-test-id="userMenuPreferencesBtn"]');
    await waitAndClick(page, '[osparc-test-id="preferencesTagsTabBtn"]');
    await waitAndClick(page, '[osparc-test-id="addTagBtn"]');
    await utils.typeInInputElement(page, '[qxclass="osparc.form.tag.TagItem"]:last-of-type input[type="text"]', TAG_NAME);
    await waitAndClick(page, '[qxclass="osparc.form.tag.TagItem"]:last-of-type [qxclass="osparc.ui.form.FetchButton"]');
    // Check tag was added
    await page.waitForFunction(tagName => {
      const el = document.querySelector(
        '[qxclass="osparc.form.tag.TagItem"]:last-of-type [qxclass="osparc.ui.basic.Tag"]'
      );
      return el && el.innerText === tagName;
    }, {}, TAG_NAME);
    // Close properties
    await waitAndClick(page, '[osparc-test-id="preferencesWindowCloseBtn"]');
  }, ourTimeout);

  test('tag shows in filters', async () => {
    // Check that tag shows in filter
    await waitAndClick(page, '[osparc-test-id="searchBarFilter-textField-study"]');
    await waitAndClick(page, '[osparc-test-id="searchBarFilter-tags-button"]');
    const tagFilterMenu = await page.waitForSelector('[osparc-test-id="searchBarFilter-tags-menu"]:not([style*="display: none"])');
    expect(await tagFilterMenu.evaluate(el => el.innerText)).toContain(TAG_NAME);
  }, ourTimeout);

  // wait until card gets unlocked. Tags will anyway be replaced by folder in the coming weeks
  test.skip('assign tag and reflect changes', async () => {
    await page.waitForSelector(
      '[qxclass="osparc.dashboard.GridButtonItem"] > [qxclass="osparc.ui.basic.Thumbnail"]',
      {
        hidden: true
      }
    );
    // Assign to study
    await waitAndClick(page, '[qxclass="osparc.dashboard.GridButtonItem"] [osparc-test-id="studyItemMenuButton"]');
    await waitAndClick(page, '[osparc-test-id="moreInfoBtn"]');
    await waitAndClick(page, '[osparc-test-id="editStudyEditTagsBtn"]');
    await waitAndClick(page, '[qxclass="osparc.form.tag.TagToggleButton"]');
    await waitAndClick(page, '[osparc-test-id="saveTagsBtn"]');
    // UI displays the change
    let displayedTag = await page.waitForSelector('[qxclass="osparc.dashboard.GridButtonItem"] [qxclass="osparc.ui.basic.Tag"]')
    await waitAndClick(page, '.qx-service-window[qxclass="osparc.ui.window.Window"] > .qx-workbench-small-cap-captionbar [qxclass="qx.ui.form.Button"]');
    expect(await displayedTag.evaluate(el => el.innerText)).toContain(TAG_NAME);
  }, ourTimeout);

  // wait until card gets unlocked. Tags will anyway be replaced by folder in the coming weeks
  test.skip('change tag and reflect changes', async () => {
    // Change the tag
    await waitAndClick(page, '[osparc-test-id="userMenuBtn"]');
    await waitAndClick(page, '[osparc-test-id="userMenuPreferencesBtn"]');
    await waitAndClick(page, '[osparc-test-id="preferencesTagsTabBtn"]');
    await waitAndClick(page, '[qxclass="osparc.form.tag.TagItem"] [qxclass="qx.ui.form.Button"]');
    await utils.clearInput(page, '[qxclass="osparc.form.tag.TagItem"] input[type="text"]');
    await utils.typeInInputElement(page, '[qxclass="osparc.form.tag.TagItem"] input[type="text"]', TAG_NAME_2);
    await waitAndClick(page, '[qxclass="osparc.form.tag.TagItem"] [qxclass="osparc.ui.form.FetchButton"]');
    await page.waitForFunction(tagName => {
      const el = document.querySelector(
        '[qxclass="osparc.form.tag.TagItem"] [qxclass="osparc.ui.basic.Tag"]'
      );
      return el && el.innerText === tagName;
    }, {}, TAG_NAME_2);
    // Close properties
    await waitAndClick(page, '[osparc-test-id="preferencesWindowCloseBtn"]');
    // Check that tag name changed in filter and study list
    await waitAndClick(page, '[osparc-test-id="searchBarFilter-textField-study"]');
    await waitAndClick(page, '[osparc-test-id="searchBarFilter-tags-button"]');
    const tagFilterMenu = await page.waitForSelector('[osparc-test-id="searchBarFilter-tags-menu"]:not([style*="display: none"])');
    expect(await tagFilterMenu.evaluate(el => el.innerText)).toContain(TAG_NAME_2);
    await page.waitForFunction(tagName => {
      const el = document.querySelector(
        '[qxclass="osparc.dashboard.GridButtonItem"] [qxclass="osparc.ui.basic.Tag"]'
      );
      return el && el.innerText === tagName;
    }, {}, TAG_NAME_2);
  }, ourTimeout);
});
