/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.TutorialBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function() {
    this._resourceType = "template";

    this.base(arguments);
  },

  members: {
    __updateAllButton: null,

    // overridden
    initResources: function() {
      if (this._resourcesInitialized) {
        return;
      }
      this._resourcesInitialized = true;

      this._showLoadingPage(this.tr("Loading Tutorials..."));
      osparc.store.Templates.getTutorials()
        .then(() => {
          this._resourcesList = [];
          this.getChildControl("resources-layout");
          this.reloadResources();
          this.__attachEventHandlers();
        });
    },

    reloadResources: function(useCache = true) {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        this.__reloadTutorials(useCache)
          .finally(() => this._hideLoadingPage());
      } else {
        this.__setResourcesToList([]);
        this._hideLoadingPage();
      }
    },

    __attachEventHandlers: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      socket.on("projectStateUpdated", data => {
        if (data) {
          const templateId = data["project_uuid"];
          const state = ("data" in data) ? data.data : {};
          const errors = ("errors" in data) ? data.errors : [];
          this.__tutorialStateReceived(templateId, state, errors);
        }
      }, this);
    },

    __tutorialStateReceived: function(templateId, state, errors) {
      const idx = this._resourcesList.findIndex(study => study["uuid"] === templateId);
      if (idx > -1) {
        this._resourcesList[idx]["state"] = state;
      }
      const templateItem = this._resourcesContainer.getCards().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === templateId);
      if (templateItem) {
        templateItem.setState(state);
      }
      if (errors.length) {
        console.error(errors);
      }
    },

    __reloadTutorials: function(useCache) {
      this.__tasksToCards();

      return osparc.store.Templates.getTutorials(useCache)
        .then(tutorials => this.__setResourcesToList(tutorials))
        .catch(() => this.__setResourcesToList([]));
    },

    _updateTutorialData: function(templateData) {
      templateData["resourceType"] = "tutorial";

      this._updateTemplateData(templateData);
    },

    __setResourcesToList: function(tutorialsList) {
      tutorialsList.forEach(tutorial => tutorial["resourceType"] = "tutorial");
      this._resourcesList = tutorialsList;
      this._reloadCards();
    },

    _reloadCards: function() {
      if (this._resourcesContainer === null) {
        return;
      }

      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("templates");
      cards.forEach(card => {
        card.setMultiSelectionMode(this.getMultiSelection());
        card.addListener("tap", () => this.__itemClicked(card), this);
        card.addListener("changeUpdatable", () => this.__evaluateUpdateAllButton(), this);
        card.addListener("changeVisibility", () => this.__evaluateUpdateAllButton(), this);
        this._populateCardMenu(card);
      });
      this.__evaluateUpdateAllButton();
      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __itemClicked: function(card) {
      if (!card.getBlocked()) {
        const templateData = this.__getTemplateData(card.getUuid());
        this._openResourceDetails(templateData);
      }
      this.resetSelection();
    },

    // LAYOUT //
    _createLayout: function() {
      this._createSearchBar();
      this._createResourcesLayout("templatesList");

      const updateAllButton = this.__createUpdateAllButton();
      if (updateAllButton) {
        this._toolbar.add(updateAllButton);
      }

      this._toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this._addGroupByButton();
      this._addViewModeButton();

      this._addResourceFilter();

      this._resourcesContainer.addListener("changeVisibility", () => this.__evaluateUpdateAllButton());

      return this._resourcesContainer;
    },

    __createUpdateAllButton: function() {
      const updateAllButton = this.__updateAllButton = new osparc.ui.form.FetchButton(this.tr("Update all")).set({
        appearance: "form-button-outlined"
      });
      updateAllButton.exclude();
      updateAllButton.addListener("tap", () => {
        const templatesAlias = osparc.product.Utils.getTemplateAlias({plural: true});
        const msg = this.tr("Are you sure you want to update all ") + templatesAlias + "?";
        const win = new osparc.ui.window.Confirmation(msg).set({
          caption: this.tr("Update") + " " + templatesAlias,
          confirmText: this.tr("Update all"),
          confirmAction: "create"
        });
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__updateAllTemplates();
          }
        }, this);
      });
      return updateAllButton;
    },

    __evaluateUpdateAllButton: function() {
      if (this._resourcesContainer) {
        const visibleCards = this._resourcesContainer.getCards().filter(card => card.isVisible());
        const anyUpdatable = visibleCards.some(card => (card.getUpdatable() !== null && osparc.data.model.Study.canIWrite(card.getResourceData()["accessRights"])));
        this.__updateAllButton.setVisibility(anyUpdatable ? "visible" : "excluded");
      }
    },

    __updateAllTemplates: async function() {
      if (this._resourcesContainer) {
        this.__updateAllButton.setFetching(true);
        const visibleCards = this._resourcesContainer.getCards().filter(card => card.isVisible());
        const updatableCards = visibleCards.filter(card => (card.getUpdatable() !== null && osparc.data.model.Study.canIWrite(card.getResourceData()["accessRights"])));
        const templatesData = [];
        updatableCards.forEach(card => templatesData.push(card.getResourceData()));
        const uniqueTemplatesUuids = [];
        const uniqueTemplatesData = templatesData.filter(templateData => {
          const isDuplicate = uniqueTemplatesUuids.includes(templateData.uuid);
          if (!isDuplicate) {
            uniqueTemplatesUuids.push(templateData.uuid);
            return true;
          }
          return false;
        });
        await this.__updateTemplates(uniqueTemplatesData);

        this.__updateAllButton.setFetching(false);
      }
    },

    __updateTemplates: async function(uniqueTemplatesData) {
      for (const uniqueTemplateData of uniqueTemplatesData) {
        const studyData = osparc.data.model.Study.deepCloneStudyObject(uniqueTemplateData);
        const templatePromises = [];
        for (const nodeId in studyData["workbench"]) {
          const node = studyData["workbench"][nodeId];
          const latestCompatible = osparc.store.Services.getLatestCompatible(node["key"], node["version"]);
          if (latestCompatible && (node["key"] !== latestCompatible["key"] || node["version"] !== latestCompatible["version"])) {
            const patchData = {};
            if (node["key"] !== latestCompatible["key"]) {
              patchData["key"] = latestCompatible["key"];
            }
            if (node["version"] !== latestCompatible["version"]) {
              patchData["version"] = latestCompatible["version"];
            }
            templatePromises.push(osparc.store.Study.patchNodeData(uniqueTemplateData, nodeId, patchData));
          }
        }
        Promise.all(templatePromises)
          .then(() => this._updateTutorialData(uniqueTemplateData))
          .catch(err => {
            osparc.FlashMessenger.logError(err);
          });
      }
    },
    // LAYOUT //

    // MENU //
    _populateCardMenu: function(card) {
      this._populateTemplateCardMenu(card);
    },

    __getTemplateData: function(id) {
      return this._resourcesList.find(template => template.uuid === id);
    },

    _deleteResourceRequested: function(templateId) {
      this._deleteTemplateRequested(this.__getTemplateData(templateId));
    },
    // MENU //

    // TASKS //
    __tasksToCards: function() {
      const tasks = osparc.store.PollTasks.getInstance().getPublishTemplateTasks();
      tasks.forEach(task => {
        const studyName = "";
        this.taskToTemplateReceived(task, studyName);
      });
    },
    // TASKS //
  }
});
