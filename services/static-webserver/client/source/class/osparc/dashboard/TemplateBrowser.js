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

qx.Class.define("osparc.dashboard.TemplateBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function(templateType) {
    this._resourceType = "template";
    this.__templateType = templateType || null;

    this.base(arguments);
  },

  members: {
    __templateType: null,
    __updateAllButton: null,

    // overridden
    initResources: function() {
      this._resourcesList = [];
      this.getChildControl("resources-layout");
      this.reloadResources();
      this.__attachEventHandlers();
      this._hideLoadingPage();
    },

    reloadResources: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        this.__reloadTemplates();
      } else {
        this.__setResourcesToList([]);
      }
    },

    invalidateTemplates: function() {
      osparc.store.Store.getInstance().invalidate("templates");
    },

    __attachEventHandlers: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      socket.on("projectStateUpdated", data => {
        if (data) {
          const templateId = data["project_uuid"];
          const state = ("data" in data) ? data.data : {};
          const errors = ("errors" in data) ? data.errors : [];
          this.__templateStateReceived(templateId, state, errors);
        }
      }, this);
    },

    __templateStateReceived: function(templateId, state, errors) {
      osparc.store.Store.getInstance().setTemplateState(templateId, state);
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

    __reloadTemplates: function() {
      this.__tasksToCards();

      osparc.data.Resources.getInstance().getAllPages("templates")
        .then(templates => this.__setResourcesToList(templates))
        .catch(err => {
          console.error(err);
          this.__setResourcesToList([]);
        });
    },

    _updateTemplateData: function(templateData) {
      templateData["resourceType"] = "template";
      const templatesList = this._resourcesList;
      const index = templatesList.findIndex(template => template["uuid"] === templateData["uuid"]);
      if (index !== -1) {
        templatesList[index] = templateData;
        this._reloadCards();
      }
    },

    __setResourcesToList: function(templatesList) {
      templatesList.forEach(template => template["resourceType"] = "template");
      if (this.__templateType === "tutorial") {
        this._resourcesList = templatesList.filter(template => [null, "tutorial"].includes(osparc.study.Utils.extractTemplateType(template)));
      } else {
        this._resourcesList = templatesList.filter(template => osparc.study.Utils.extractTemplateType(template) === this.__templateType);
      }
      this.fireDataEvent("showTab", Boolean(this._resourcesList.length));

      this._reloadCards();
    },

    _reloadCards: function() {
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
          .then(() => this._updateTemplateData(uniqueTemplateData))
          .catch(err => {
            osparc.FlashMessenger.logError(err);
          });
      }
    },
    // LAYOUT //

    // MENU //
    _populateCardMenu: function(card) {
      const menu = card.getMenu();
      const templateData = card.getResourceData();

      const editButton = this.__getEditTemplateMenuButton(templateData);
      if (editButton) {
        menu.add(editButton);
        menu.addSeparator();
      }

      const openButton = this._getOpenMenuButton(templateData);
      if (openButton) {
        menu.add(openButton);
      }

      const shareButton = this._getShareMenuButton(card);
      if (shareButton) {
        menu.add(shareButton);
      }

      const tagsButton = this._getTagsMenuButton(card);
      if (tagsButton) {
        menu.add(tagsButton);
      }

      const deleteButton = this.__getDeleteTemplateMenuButton(templateData);
      if (deleteButton && editButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }
    },

    __getEditTemplateMenuButton: function(templateData) {
      const isCurrentUserOwner = osparc.data.model.Study.canIWrite(templateData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const editButton = new qx.ui.menu.Button(this.tr("Open"));
      editButton.addListener("execute", () => this.__editTemplate(templateData), this);
      return editButton;
    },

    __getTemplateData: function(id) {
      return this._resourcesList.find(template => template.uuid === id);
    },

    _deleteResourceRequested: function(templateId) {
      this.__deleteTemplateRequested(this.__getTemplateData(templateId));
    },

    __deleteTemplateRequested: function(templateData) {
      const rUSure = this.tr("Are you sure you want to delete ");
      const msg = rUSure + "<b>" + templateData.name + "</b>?";
      const win = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          this.__doDeleteTemplate(templateData);
        }
      }, this);
    },

    __getDeleteTemplateMenuButton: function(templateData) {
      const isCurrentUserOwner = osparc.data.model.Study.canIDelete(templateData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/12");
      deleteButton.set({
        appearance: "menu-button"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => this.__deleteTemplateRequested(templateData), this);
      return deleteButton;
    },

    __editTemplate: function(studyData) {
      const isStudyCreation = false;
      this._startStudyById(studyData.uuid, null, null, isStudyCreation);
    },

    __doDeleteTemplate: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        const arCopy = osparc.utils.Utils.deepCloneObject(studyData["accessRights"]);
        // remove collaborator
        delete arCopy[myGid];
        operationPromise = osparc.store.Study.patchStudyData(studyData, "accessRights", arCopy);
      } else {
        // delete study
        operationPromise = osparc.store.Store.getInstance().deleteStudy(studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromTemplateList(studyData.uuid))
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __removeFromTemplateList: function(templateId) {
      const idx = this._resourcesList.findIndex(study => study["uuid"] === templateId);
      if (idx > -1) {
        this._resourcesList.splice(idx, 1);
      }
      this._resourcesContainer.removeCard(templateId);
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

    taskToTemplateReceived: function(task, studyName) {
      const toTemplateTaskUI = new osparc.task.ToTemplate(studyName);
      toTemplateTaskUI.setTask(task);

      osparc.task.TasksContainer.getInstance().addTaskUI(toTemplateTaskUI);

      const cardTitle = this.tr("Publishing ") + studyName;
      const toTemplateCard = this._addTaskCard(task, cardTitle, osparc.task.ToTemplate.ICON);
      if (toTemplateCard) {
        this.__attachToTemplateEventHandler(task, toTemplateCard);
      }
    },

    __attachToTemplateEventHandler: function(task, toTemplateCard) {
      const finished = () => {
        this._resourcesContainer.removeNonResourceCard(toTemplateCard);
      };

      task.addListener("updateReceived", e => {
        const updateData = e.getData();
        if ("task_progress" in updateData && toTemplateCard) {
          const taskProgress = updateData["task_progress"];
          toTemplateCard.getChildControl("progress-bar").set({
            value: osparc.data.PollTask.extractProgress(updateData) * 100
          });
          toTemplateCard.getChildControl("state-label").set({
            value: taskProgress["message"]
          });
        }
      }, this);
      task.addListener("resultReceived", e => {
        finished();
        this.reloadResources();
        const msg = this.tr("Template created");
        osparc.FlashMessenger.logAs(msg, "INFO");
      });
      task.addListener("taskAborted", () => {
        finished();
        const msg = this.tr("Study to Template cancelled");
        osparc.FlashMessenger.logAs(msg, "WARNING");
      });
      task.addListener("pollingError", e => {
        finished();
        const err = e.getData();
        osparc.FlashMessenger.logError(err);
      });
    },
    // TASKS //
  }
});
