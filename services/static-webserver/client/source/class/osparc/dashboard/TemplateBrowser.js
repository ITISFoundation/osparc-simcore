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

  members: {
    __updateAllButton: null,

    // overridden
    initResources: function() {
      this._resourcesList = [];
      const preResourcePromises = [];
      const store = osparc.store.Store.getInstance();
      preResourcePromises.push(store.getAllServices());
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        preResourcePromises.push(osparc.data.Resources.get("tags"));
      }

      Promise.all(preResourcePromises)
        .then(() => {
          this.getChildControl("resources-layout");
          this.reloadResources();
          this.__attachEventHandlers();
          this._hideLoadingPage();
        })
        .catch(err => console.error(err));
    },

    reloadResources: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        this.__reloadTemplates();
      } else {
        this.__setResourcesToList([]);
      }
    },

    __attachEventHandlers: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      const slotName = "projectStateUpdated";
      socket.on(slotName, jsonString => {
        const data = JSON.parse(jsonString);
        if (data) {
          const templateId = data["project_uuid"];
          const state = ("data" in data) ? data["data"] : {};
          const errors = ("errors" in data) ? data["errors"] : [];
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
      this._resourcesList = templatesList;
      this._reloadCards();
    },

    _reloadCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("templatesList");
      cards.forEach(card => {
        card.addListener("execute", () => this.__itemClicked(card), this);
        this._populateCardMenu(card);
      });
      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __itemClicked: function(card) {
      const matchesId = study => study.uuid === card.getUuid();
      const templateData = this._resourcesList.find(matchesId);
      this.__createStudyFromTemplate(templateData);
      this.resetSelection();
    },

    __createStudyFromTemplate: function(templateData) {
      if (!this._checkLoggedIn()) {
        return;
      }

      this._showLoadingPage(this.tr("Creating ") + (templateData.name || this.tr("Study")));
      osparc.utils.Study.createStudyFromTemplate(templateData, this._loadingPage)
        .then(studyId => {
          this._hideLoadingPage();
          this.__startStudy(studyId, templateData);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __startStudy: function(studyId, templateData) {
      if (!this._checkLoggedIn()) {
        return;
      }

      const defaultContext = "workbench";
      let pageContext = defaultContext;
      if (templateData !== undefined) {
        pageContext = osparc.data.model.Study.getUiMode(templateData) || defaultContext;
      }

      const data = {
        studyId,
        pageContext
      };
      this.fireDataEvent("startStudy", data);
    },

    // LAYOUT //
    _createLayout: function() {
      this._createResourcesLayout("template");
      const list = this._resourcesContainer.getFlatList();
      if (list) {
        osparc.utils.Utils.setIdToWidget(list, "templatesList");
      }

      const updateAllButton = this.__createUpdateAllButton();
      if (updateAllButton) {
        this._secondaryBar.add(updateAllButton);
      }

      this._secondaryBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this._addGroupByButton();
      this._addViewModeButton();

      this._resourcesContainer.addListener("changeVisibility", () => this.__evaluateUpdateAllButton());

      return this._resourcesContainer;
    },

    __createUpdateAllButton: function() {
      const updateAllButton = this.__updateAllButton = new qx.ui.form.Button(this.tr("Update All"));
      updateAllButton.exclude();
      updateAllButton.addListener("tap", () => {
        const msg = this.tr("Are you sure you want to update all templates?");
        const win = new osparc.ui.window.Confirmation(msg).set({
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
        const anyUpdatable = this._resourcesContainer.getCards().some(card => {
          if (card.getUpdatable() !== null && osparc.data.model.Study.canIWrite(card.getResourceData()["accessRights"])) {
            return true;
          }
          return false;
        });
        this.__updateAllButton.setVisibility(anyUpdatable ? "visible" : "excluded");
      }
    },

    __updateAllServices: function(nodeIds, button) {
      this.setEnabled(false);
      for (const nodeId in this._studyData["workbench"]) {
        if (nodeIds.includes(nodeId)) {
          const node = this._studyData["workbench"][nodeId];
          const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(this._services, node["key"], node["version"]);
          this._studyData["workbench"][nodeId]["version"] = latestCompatibleMetadata["version"];
        }
      }
      this._updateStudy(button);
    },
    // LAYOUT //

    // MENU //
    _populateCardMenu: function(card) {
      const menu = card.getMenu();
      const studyData = card.getResourceData();

      const editButton = this.__getEditTemplateMenuButton(studyData);
      if (editButton) {
        menu.add(editButton);
        menu.addSeparator();
      }

      const shareButton = this._getShareMenuButton(card);
      if (shareButton) {
        menu.add(shareButton);
      }

      const moreInfoButton = this._getMoreOptionsMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      const deleteButton = this.__getDeleteTemplateMenuButton(studyData);
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

      const editButton = new qx.ui.menu.Button(this.tr("Edit"));
      editButton.addListener("execute", () => this.__editTemplate(templateData), this);
      return editButton;
    },

    __getDeleteTemplateMenuButton: function(templateData) {
      const isCurrentUserOwner = osparc.data.model.Study.canIDelete(templateData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => {
        const win = this.__createConfirmWindow(templateData.name);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteTemplate(templateData);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __createConfirmWindow: function(templateName) {
      const rUSure = this.tr("Are you sure you want to delete ");
      const msg = rUSure + "<b>" + templateName + "</b>?";
      const confWin = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      return confWin;
    },
    __editTemplate: function(studyData) {
      // osparc.data.Resources.fetch("studies", "open", params);
      this.__startStudy(studyData.uuid);
    },
    __deleteTemplate: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      const params = {
        url: {
          "studyId": studyData.uuid
        }
      };
      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        // remove collaborator
        osparc.component.permissions.Study.removeCollaborator(studyData, myGid);
        params["data"] = studyData;
        operationPromise = osparc.data.Resources.fetch("templates", "put", params);
      } else {
        // delete study
        operationPromise = osparc.data.Resources.fetch("templates", "delete", params, studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromTemplateList(studyData.uuid))
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        });
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
    __attachToTemplateEventHandler: function(task, taskUI, toTemplateCard) {
      const finished = (msg, msgLevel) => {
        if (msg) {
          osparc.component.message.FlashMessenger.logAs(msg, msgLevel);
        }
        taskUI.stop();
        this._resourcesContainer.removeNonResourceCard(toTemplateCard);
      };

      task.addListener("taskAborted", () => {
        const msg = this.tr("Study to Template cancelled");
        finished(msg, "INFO");
      });
      task.addListener("updateReceived", e => {
        const updateData = e.getData();
        if ("task_progress" in updateData && toTemplateCard) {
          const progress = updateData["task_progress"];
          toTemplateCard.getChildControl("progress-bar").set({
            value: progress["percent"]*100
          });
          toTemplateCard.getChildControl("state-label").set({
            value: progress["message"]
          });
        }
      }, this);
      task.addListener("resultReceived", e => {
        finished();
        this.reloadResources();
      });
      task.addListener("pollingError", e => {
        const errMsg = e.getData();
        const msg = this.tr("Something went wrong Publishing the study<br>") + errMsg;
        finished(msg, "ERROR");
      });
    },

    _taskDataReceived: function(taskData) {
      // a bit hacky
      if (taskData["task_id"].includes("from_study") && taskData["task_id"].includes("as_template")) {
        const interval = 1000;
        const pollTasks = osparc.data.PollTasks.getInstance();
        const task = pollTasks.addTask(taskData, interval);
        if (task === null) {
          return;
        }
        // ask backend for studyData?
        const studyName = "";
        this.taskToTemplateReceived(task, studyName);
      }
    },

    taskToTemplateReceived: function(task, studyName) {
      const toTemaplateTaskUI = new osparc.component.task.ToTemplate(studyName);
      toTemaplateTaskUI.setTask(task);
      toTemaplateTaskUI.start();
      const toTemplateCard = this.__createToTemplateCard(studyName);
      toTemplateCard.setTask(task);
      this.__attachToTemplateEventHandler(task, toTemaplateTaskUI, toTemplateCard);
    },

    __createToTemplateCard: function(studyName) {
      const isGrid = this._resourcesContainer.getMode() === "grid";
      const toTemplateCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      toTemplateCard.buildLayout(
        this.tr("Publishing ") + studyName,
        osparc.component.task.ToTemplate.ICON + (isGrid ? "60" : "24"),
        null,
        true
      );
      toTemplateCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addNonResourceCard(toTemplateCard);
      return toTemplateCard;
    }
    // TASKS //
  }
});
