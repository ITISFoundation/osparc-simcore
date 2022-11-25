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
    __templates: null,

    // overridden
    initResources: function() {
      this.__templates = [];
      const preResourcePromises = [];
      const store = osparc.store.Store.getInstance();
      preResourcePromises.push(store.getServicesOnly());
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        preResourcePromises.push(osparc.data.Resources.get("tags"));
      }

      Promise.all(preResourcePromises)
        .then(() => {
          this.getChildControl("resources-layout");
          this.reloadResources();
          this._hideLoadingPage();
        })
        .catch(err => console.error(err));
    },

    reloadResources: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        this.__reloadTemplates();
      } else {
        this._resetResourcesList([]);
      }
    },

    __reloadTemplates: function() {
      osparc.data.Resources.getInstance().getAllPages("templates")
        .then(templates => {
          this._addResourcesToList(templates);
        })
        .catch(err => {
          console.error(err);
          this._addResourcesToList([]);
        });
    },

    _createLayout: function() {
      this._createResourcesLayout("template");
      osparc.utils.Utils.setIdToWidget(this._resourcesContainer, "templatesList");

      const groupByButton = this.__createGroupByButton();
      this._secondaryBar.add(groupByButton);

      this._resourcesContainer.addListener("changeMode", () => this._resetResourcesList());

      return this._resourcesContainer;
    },

    __createGroupByButton: function() {
      const groupByMenu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const groupByButton = new qx.ui.form.MenuButton(this.tr("Group by"), null, groupByMenu);

      const groupByChanged = groupBy => {
        this._resourcesContainer.setGroupBy(groupBy);
        this._resourcesContainer.setResourcesData(this.__templates);
      };
      const dontGroup = new qx.ui.menu.RadioButton(this.tr("Don't group"));
      dontGroup.addListener("execute", () => groupByChanged(null));
      const tagByGroup = new qx.ui.menu.RadioButton(this.tr("Tags"));
      tagByGroup.addListener("execute", () => groupByChanged("tags"));

      const groupOptions = new qx.ui.form.RadioGroup();
      [
        dontGroup,
        tagByGroup
      ].forEach(btn => {
        groupByMenu.add(btn);
        groupOptions.add(btn);
      });

      return groupByButton;
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

    _resetTemplateItem: function(templateData) {
      const templatesList = this.__templates;
      const index = templatesList.findIndex(template => template["uuid"] === templateData["uuid"]);
      if (index === -1) {
        templatesList.push(templateData);
      } else {
        templatesList[index] = templateData;
      }
      this._resetResourcesList(templatesList);
    },

    // overriden
    _resetResourcesList: function(templatesList) {
      if (templatesList === undefined) {
        templatesList = this.__templates;
      }
      this._removeResourceCards();
      this._addResourcesToList(templatesList);
    },

    _addResourcesToList: function(templatesList) {
      const cards = this._resourcesContainer.getCards();
      templatesList.forEach(template => {
        if (this.__templates.indexOf(template) === -1) {
          this.__templates.push(template);
        }
        template["resourceType"] = "template";
        const exists = cards.findIndex(card => card.getUuid() === template["uuid"]);
        if (exists !== -1) {
          return;
        }
        const templateItem = this.__createTemplateItem(template);
        this._resourcesContainer.add(templateItem);
      });

      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __removeFromTemplateList: function(templateId) {
      const idx = this.__templates.findIndex(study => study["uuid"] === templateId);
      if (idx > -1) {
        this.__templates.splice(idx, 1);
      }
      this._resourcesContainer.removeCard(templateId);
    },

    __createTemplateItem: function(templateData) {
      const item = this._createResourceItem(templateData);
      item.addListener("execute", () => this.__itemClicked(item), this);
      return item;
    },

    _populateCardMenu: function(menu, studyData) {
      const moreInfoButton = this._getMoreOptionsMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      const deleteButton = this.__getDeleteTemplateMenuButton(studyData);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }
    },

    __getDeleteTemplateMenuButton: function(templateData) {
      const isCurrentUserOwner = osparc.data.model.Study.isOwner(templateData);
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

    __itemClicked: function(item) {
      const matchesId = study => study.uuid === item.getUuid();
      const templateData = this.__templates.find(matchesId);
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
      this._resourcesContainer.addAt(toTemplateCard, 0);
      return toTemplateCard;
    },

    __attachToTemplateEventHandler: function(task, taskUI, toTemplateCard) {
      const finished = (msg, msgLevel) => {
        if (msg) {
          osparc.component.message.FlashMessenger.logAs(msg, msgLevel);
        }
        taskUI.stop();
        this._resourcesContainer.remove(toTemplateCard);
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

    taskToTemplateReceived: function(task, studyName) {
      const toTemaplateTaskUI = new osparc.component.task.ToTemplate(studyName);
      toTemaplateTaskUI.setTask(task);
      toTemaplateTaskUI.start();
      const toTemplateCard = this.__createToTemplateCard(studyName);
      toTemplateCard.setTask(task);
      this.__attachToTemplateEventHandler(task, toTemaplateTaskUI, toTemplateCard);
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

    __createConfirmWindow: function(templateName) {
      const rUSure = this.tr("Are you sure you want to delete ");
      const msg = rUSure + "<b>" + templateName + "</b>?";
      const confWin = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      return confWin;
    }
  }
});
