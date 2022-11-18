/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows lists user's studies.
 *
 * It is the entry point to start editing or creating a new study.
 *
 * Also takes care of retrieveing the list of services and pushing the changes in the metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let studyBrowser = new osparc.dashboard.StudyBrowser();
 *   this.getRoot().add(studyBrowser);
 * </pre>
 */

qx.Class.define("osparc.dashboard.StudyBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  statics: {
    EXPECTED_TI_TEMPLATE_TITLE: "TI Planning Tool",
    EXPECTED_S4L_SERVICE_KEYS: {
      "simcore/services/dynamic/jupyter-smash": {
        title: "Start sim4life lab",
        decription: "jupyter powered by s4l",
        idToWidget: "startJSmashButton"
      },
      "simcore/services/dynamic/sim4life-dy": {
        title: "Start sim4life",
        decription: "New sim4life project",
        idToWidget: "startS4LButton"
      }
    },
    EXPECTED_S4L_LIGHT_SERVICE_KEYS: {
      "simcore/services/dynamic/sim4life-dy": {
        title: "Start sim4life",
        decription: "New sim4life project",
        idToWidget: "startS4LButton"
      }
    }
  },

  properties: {
    multiSelection: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelection",
      apply: "__applyMultiSelection"
    }
  },

  members: {
    __studies: null,

    reloadStudy: function(studyId) {
      const params = {
        url: {
          "studyId": studyId
        }
      };
      return osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this._resetStudyItem(studyData);
        })
        .catch(err => console.error(err));
    },

    reloadResources: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.user.read")) {
        this._requestResources(false);
      } else {
        this._resetResourcesList([]);
      }
    },

    invalidateStudies: function() {
      osparc.store.Store.getInstance().invalidate("studies");
      this._resetResourcesList([]);
      this._resourcesContainer.nextRequest = null;
    },

    // overridden
    initResources: function() {
      this.__studies = [];
      const preResourcePromises = [];
      const store = osparc.store.Store.getInstance();
      preResourcePromises.push(store.getVisibleMembers());
      preResourcePromises.push(store.getServicesOnly());
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        preResourcePromises.push(osparc.data.Resources.get("tags"));
      }
      Promise.all(preResourcePromises)
        .then(() => {
          this.getChildControl("resources-layout");
          this.__reloadResources();
          this.__attachEventHandlers();
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            this.__getStudyAndStart(loadStudyId);
          }
          this._hideLoadingPage();
        })
        .catch(console.error);
    },

    __reloadResources: function() {
      this.__getActiveStudy();
      this.reloadResources();
    },

    __getActiveStudy: function() {
      const params = {
        url: {
          tabId: osparc.utils.Utils.getClientSessionID()
        }
      };
      osparc.data.Resources.fetch("studies", "getActive", params)
        .then(studyData => {
          if (studyData) {
            this.__startStudy(studyData);
          } else {
            osparc.store.Store.getInstance().setCurrentStudyId(null);
          }
        })
        .catch(err => {
          console.error(err);
        });
    },

    __addNewStudyButtons: function(mode = "grid") {
      this.__addNewStudyButton(mode);
      if (osparc.utils.Utils.isProduct("tis")) {
        this.__removeNewStudyButtons();
        this.__addNewPlanButton(mode);
      } else if (osparc.utils.Utils.isProduct("s4l")) {
        this.__addNewS4LServiceButtons(mode);
      } else if (osparc.utils.Utils.isProduct("s4llite")) {
        this.__removeNewStudyButtons();
        this.__addNewS4LLiteServiceButtons(mode);
      }
    },

    __removeNewStudyButtons: function() {
      const cards = this._resourcesContainer.getChildren();
      for (let i=cards.length-1; i>=0; i--) {
        const card = cards[i];
        if (osparc.dashboard.ResourceBrowserBase.isCardNewItem(card)) {
          this._resourcesContainer.remove(card);
        }
      }
    },

    __addNewStudyButton: function(mode) {
      const newStudyBtn = (mode === "grid") ? new osparc.dashboard.GridButtonNew() : new osparc.dashboard.ListButtonNew();
      newStudyBtn.subscribeToFilterGroup("searchBarFilter");
      osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
      newStudyBtn.addListener("execute", () => this.__newStudyBtnClicked(newStudyBtn));
      if (this._resourcesContainer.getMode() === "list") {
        const width = this._resourcesContainer.getBounds().width - 15;
        newStudyBtn.setWidth(width);
      }
      this._resourcesContainer.addAt(newStudyBtn, 0);
    },

    __addNewPlanButton: function(mode) {
      osparc.data.Resources.get("templates")
        .then(templates => {
          // replace if a "TI Planning Tool" template exists
          const templateData = templates.find(t => t.name === this.self().EXPECTED_TI_TEMPLATE_TITLE);
          if (templateData) {
            const title = this.tr("New Plan");
            const desc = this.tr("Start a new plan");
            const newPlanButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
            osparc.utils.Utils.setIdToWidget(newPlanButton, "newPlanButton");
            newPlanButton.addListener("execute", () => this.__newPlanBtnClicked(newPlanButton, templateData));
            if (this._resourcesContainer.getMode() === "list") {
              const width = this._resourcesContainer.getBounds().width - 15;
              newPlanButton.setWidth(width);
            }
            this._resourcesContainer.addAt(newPlanButton, 0);
          }
        });
    },

    __addNewStudyFromServiceButtons: function(mode, services, serviceKey, newButtonInfo) {
      // Make sure we have access to that service
      const versions = osparc.utils.Services.getVersions(services, serviceKey);
      if (versions.length && newButtonInfo) {
        const title = newButtonInfo.title;
        const desc = newButtonInfo.decription;
        const newStudyFromServiceButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
        osparc.utils.Utils.setIdToWidget(newStudyFromServiceButton, newButtonInfo.idToWidget);
        newStudyFromServiceButton.addListener("execute", () => this.__newStudyFromServiceBtnClicked(newStudyFromServiceButton, serviceKey, versions[versions.length-1]));
        if (this._resourcesContainer.getMode() === "list") {
          const width = this._resourcesContainer.getBounds().width - 15;
          newStudyFromServiceButton.setWidth(width);
        }
        this._resourcesContainer.addAt(newStudyFromServiceButton, 0);
      }
    },

    __addNewS4LServiceButtons: function(mode) {
      const store = osparc.store.Store.getInstance();
      store.getServicesOnly(false)
        .then(services => {
          // add new plus buttons if key services exists
          const newButtonsInfo = this.self().EXPECTED_S4L_SERVICE_KEYS;
          Object.keys(newButtonsInfo).forEach(serviceKey => {
            this.__addNewStudyFromServiceButtons(mode, services, serviceKey, newButtonsInfo[serviceKey]);
          });
        });
    },

    __addNewS4LLiteServiceButtons: function(mode) {
      const store = osparc.store.Store.getInstance();
      store.getServicesOnly(false)
        .then(services => {
          // add new plus buttons if key services exists
          const newButtonsInfo = this.self().EXPECTED_S4L_LIGHT_SERVICE_KEYS;
          Object.keys(newButtonsInfo).forEach(serviceKey => {
            this.__addNewStudyFromServiceButtons(mode, services, serviceKey, newButtonsInfo[serviceKey]);
          });
        });
    },

    _createLayout: function() {
      this._createResourcesLayout("study");

      const importStudyButton = this.__createImportButton();
      this._secondaryBar.add(importStudyButton);
      importStudyButton.exclude();
      osparc.utils.DisabledPlugins.isImportDisabled()
        .then(isDisabled => {
          importStudyButton.setVisibility(isDisabled ? "excluded" : "visible");
        });

      this._secondaryBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const studiesDeleteButton = this.__createDeleteButton(false);
      this._secondaryBar.add(studiesDeleteButton);

      const selectStudiesButton = this.__createSelectButton();
      this._secondaryBar.add(selectStudiesButton);

      osparc.utils.Utils.setIdToWidget(this._resourcesContainer, "studiesList");

      this.__addNewStudyButtons();

      const loadingStudiesBtn = this._createLoadMoreButton("studiesLoading");
      this._resourcesContainer.add(loadingStudiesBtn);

      this.addListener("changeMultiSelection", e => {
        const multiEnabled = e.getData();
        const cards = this._resourcesContainer.getChildren();
        cards.forEach(card => {
          if (!osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)) {
            card.setEnabled(!multiEnabled);
          }
        });
        importStudyButton.setEnabled(!multiEnabled);
      });

      this._resourcesContainer.bind("selection", studiesDeleteButton, "visibility", {
        converter: selection => selection.length ? "visible" : "excluded"
      });
      this._resourcesContainer.bind("selection", studiesDeleteButton, "label", {
        converter: selection => selection.length > 1 ? this.tr("Delete selected")+" ("+selection.length+")" : this.tr("Delete")
      });

      this._resourcesContainer.addListener("changeVisibility", () => this._moreResourcesRequired());

      this._resourcesContainer.addListener("changeMode", () => {
        this._resetResourcesList();

        this.__removeNewStudyButtons();
        this.__addNewStudyButtons(this._resourcesContainer.getMode());

        const cards = this._resourcesContainer.getChildren();
        cards.forEach(card => {
          if (card === this._loadingResourcesBtn) {
            const fetching = card.getFetching();
            const visibility = card.getVisibility();
            this._resourcesContainer.remove(card);
            const newLoadMoreBtn = this._createLoadMoreButton("studiesLoading", this._resourcesContainer.getMode());
            newLoadMoreBtn.set({
              fetching,
              visibility
            });
            this._resourcesContainer.add(newLoadMoreBtn);
          }
        });
      }, this);

      return this._resourcesContainer;
    },

    __createImportButton: function() {
      const importButton = new qx.ui.form.Button(this.tr("Import"));
      importButton.addListener("execute", () => {
        const importStudy = new osparc.component.study.Import();
        const win = osparc.ui.window.Window.popUpInWindow(importStudy, this.tr("Import Study"), 400, 125);
        win.set({
          clickAwayClose: false
        });
        importStudy.addListener("fileReady", e => {
          win.close();
          const file = e.getData();
          if (file === null || file === undefined) {
            return;
          }
          const size = file.size;
          const maxSize = 10 * 1024 * 1024 * 1024; // 10 GB
          if (size > maxSize) {
            osparc.component.message.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          this.__importStudy(file);
        }, this);
      }, this);
      return importButton;
    },

    __createDeleteButton: function() {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14");
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteStudiesBtn");
      deleteButton.addListener("execute", () => {
        const selection = this._resourcesContainer.getSelection();
        const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
        if (preferencesSettings.getConfirmDeleteStudy()) {
          const win = this.__createConfirmWindow(selection.map(button => button.getTitle()));
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__deleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
            }
          }, this);
        } else {
          this.__deleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
        }
      }, this);
      return deleteButton;
    },

    __createSelectButton: function() {
      const selectButton = new qx.ui.form.ToggleButton().set({
        marginRight: 8
      });
      selectButton.bind("value", this, "multiSelection");
      selectButton.bind("value", selectButton, "label", {
        converter: val => val ? this.tr("Cancel Selection") : this.tr("Select Studies")
      });
      this.bind("multiSelection", selectButton, "value");
      return selectButton;
    },

    __applyMultiSelection: function(value) {
      this._resourcesContainer.getChildren().forEach(studyItem => {
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(studyItem)) {
          studyItem.setMultiSelectionMode(value);
          if (value === false) {
            studyItem.setValue(false);
          }
        }
      });
    },

    __getStudyAndStart: function(loadStudyId) {
      const params = {
        url: {
          "studyId": loadStudyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this.__startStudy(studyData);
        })
        .catch(() => {
          const msg = this.tr("Study unavailable or inaccessible");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
    },

    __studyStateReceived: function(studyId, state, errors) {
      osparc.store.Store.getInstance().setStudyState(studyId, state);
      const idx = this.__studies.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this.__studies[idx]["state"] = state;
      }
      const studyItem = this._resourcesContainer.getChildren().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === studyId);
      if (studyItem) {
        studyItem.setState(state);
      }
      if (errors.length) {
        console.error(errors);
      }
    },

    __attachEventHandlers: function() {
      // Listen to socket
      const socket = osparc.wrapper.WebSocket.getInstance();
      // callback for incoming logs
      const slotName = "projectStateUpdated";
      socket.removeSlot(slotName);
      socket.on(slotName, function(jsonString) {
        const data = JSON.parse(jsonString);
        if (data) {
          const studyId = data["project_uuid"];
          const state = ("data" in data) ? data["data"] : {};
          const errors = ("errors" in data) ? data["errors"] : [];
          this.__studyStateReceived(studyId, state, errors);
        }
      }, this);

      const commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.resetSelection();
        this.setMultiSelection(false);
      });
      osparc.store.Store.getInstance().addListener("changeTags", () => {
        this.invalidateStudies();
        this.reloadResources();
      }, this);
    },

    __newStudyBtnClicked: function(button) {
      button.setValue(false);
      const minStudyData = osparc.data.model.Study.createMyNewStudyObject();
      const title = osparc.utils.Utils.getUniqueStudyName(minStudyData.name, this.__studies);
      minStudyData["name"] = title;
      minStudyData["description"] = "";
      this.__createStudy(minStudyData, null);
    },

    __newPlanBtnClicked: function(button, templateData) {
      button.setValue(false);
      const title = osparc.utils.Utils.getUniqueStudyName(templateData.name, this.__studies);
      templateData.name = title;
      this._showLoadingPage(this.tr("Creating ") + (templateData.name || this.tr("Study")));
      osparc.utils.Study.createStudyFromTemplate(templateData, this._loadingPage)
        .then(studyId => {
          this._hideLoadingPage();
          this.__getStudyAndStart(studyId);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __newStudyFromServiceBtnClicked: function(button, key, version) {
      button.setValue(false);
      console.log(key, version);
      this._showLoadingPage(this.tr("Creating Study"));
      osparc.utils.Study.createStudyFromService(key, version)
        .then(studyId => {
          this._hideLoadingPage();
          this.__startStudyById(studyId);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __createStudy: function(minStudyData) {
      this._showLoadingPage(this.tr("Creating ") + (minStudyData.name || this.tr("Study")));

      const params = {
        data: minStudyData
      };
      osparc.utils.Study.createStudyAndPoll(params)
        .then(studyData => {
          this._hideLoadingPage();
          this.__startStudy(studyData);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __startStudy: function(studyData, pageContext) {
      if (pageContext === undefined) {
        pageContext = osparc.data.model.Study.getUiMode(studyData) || "workbench";
      }
      this.__startStudyById(studyData["uuid"], pageContext);
    },

    __startStudyById: function(studyId, pageContext = "workbench") {
      if (!this._checkLoggedIn()) {
        return;
      }

      const data = {
        studyId,
        pageContext
      };
      this.fireDataEvent("startStudy", data);
    },

    _resetStudyItem: function(studyData) {
      const studies = this.__studies;
      const index = studies.findIndex(study => study["uuid"] === studyData["uuid"]);
      if (index === -1) {
        studies.push(studyData);
      } else {
        studies[index] = studyData;
      }
      this._resetResourcesList(studies);
    },

    // overriden
    _resetResourcesList: function(studiesList) {
      if (studiesList === undefined) {
        studiesList = this.__studies;
      }
      const studyItems = this._resourcesContainer.getChildren();
      for (let i=studyItems.length-1; i>=0; i--) {
        const studyItem = studyItems[i];
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(studyItem)) {
          this._resourcesContainer.remove(studyItem);
        }
      }
      this._addResourcesToList(studiesList);
    },

    _addResourcesToList: function(studiesList) {
      osparc.dashboard.ResourceBrowserBase.sortStudyList(studiesList);
      const studyList = this._resourcesContainer.getChildren();
      studiesList.forEach(study => {
        if (this.__studies.indexOf(study) === -1) {
          this.__studies.push(study);
        }

        study["resourceType"] = "study";
        const idx = studyList.findIndex(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === study["uuid"]);
        if (idx !== -1) {
          return;
        }
        const studyItem = this.__createStudyItem(study);
        studyItem.setMultiSelectionMode(this.getMultiSelection());
        this._resourcesContainer.add(studyItem);
      });
      osparc.dashboard.ResourceBrowserBase.sortStudyList(studyList.filter(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)));
      const idx = studyList.findIndex(card => (card instanceof osparc.dashboard.GridButtonLoadMore) || (card instanceof osparc.dashboard.ListButtonLoadMore));
      if (idx !== -1) {
        studyList.push(studyList.splice(idx, 1)[0]);
      }

      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __removeFromStudyList: function(studyId) {
      const idx = this.__studies.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this.__studies.splice(idx, 1);
      }
      const studyItem = this._resourcesContainer.getChildren().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === studyId);
      if (studyItem) {
        this._resourcesContainer.remove(studyItem);
      }
    },

    __createStudyItem: function(studyData) {
      const item = this._createResourceItem(studyData);
      item.addListener("tap", e => {
        if (!item.isLocked()) {
          this.__itemClicked(item, e.getNativeEvent().shiftKey);
        }
      }, this);
      item.addListener("updateStudy", e => {
        const updatedStudyData = e.getData();
        updatedStudyData["resourceType"] = "study";
        this._resetStudyItem(updatedStudyData);
      }, this);
      item.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));
      return item;
    },

    _getResourceItemMenu: function(studyData, item) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const renameStudyButton = this.__getRenameStudyMenuButton(studyData);
      menu.add(renameStudyButton);

      const studyDataButton = this.__getStudyDataMenuButton(studyData);
      menu.add(studyDataButton);

      const duplicateStudyButton = this.__getDuplicateMenuButton(studyData);
      menu.add(duplicateStudyButton);

      const exportButton = this.__getExportMenuButton(studyData);
      menu.add(exportButton);

      const moreOptionsButton = this._getMoreOptionsMenuButton(studyData);
      menu.add(moreOptionsButton);

      const deleteButton = this.__getDeleteStudyMenuButton(studyData, false);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }

      return menu;
    },

    __getRenameStudyMenuButton: function(studyData) {
      const renameButton = new qx.ui.menu.Button(this.tr("Rename"));
      renameButton.addListener("execute", () => {
        const renamer = new osparc.component.widget.Renamer(studyData["name"]);
        renamer.addListener("labelChanged", e => {
          const newLabel = e.getData()["newLabel"];
          const studyDataCopy = osparc.data.model.Study.deepCloneStudyObject(studyData);
          studyDataCopy.name = newLabel;
          this.__updateStudy(studyDataCopy);
          renamer.close();
        }, this);
        renamer.center();
        renamer.open();
      }, this);
      return renameButton;
    },

    __updateStudy: function(studyData) {
      const params = {
        url: {
          "studyId": studyData["uuid"]
        },
        data: studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(updatedStudyData => {
          this._resetStudyItem(updatedStudyData);
        })
        .catch(err => {
          const msg = this.tr("Something went wrong updating the Service");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
          console.error(err);
        });
    },

    __getStudyDataMenuButton: function(studyData) {
      const studyDataButton = new qx.ui.menu.Button(this.tr("Study data"));
      studyDataButton.addListener("execute", () => {
        const studyDataManager = new osparc.component.widget.NodeDataManager(studyData["uuid"]);
        osparc.ui.window.Window.popUpInWindow(studyDataManager, studyData["name"], 900, 600).set({
          appearance: "service-window"
        });
      }, this);
      return studyDataButton;
    },

    __getDuplicateMenuButton: function(studyData) {
      const duplicateButton = new qx.ui.menu.Button(this.tr("Duplicate"));
      duplicateButton.addListener("execute", () => this.__duplicateStudy(studyData), this);
      return duplicateButton;
    },

    __getExportMenuButton: function(studyData) {
      const exportButton = new qx.ui.menu.Button(this.tr("Export"));
      exportButton.exclude();
      osparc.utils.DisabledPlugins.isExportDisabled()
        .then(isDisabled => {
          exportButton.setVisibility(isDisabled ? "excluded" : "visible");
        });
      exportButton.addListener("execute", () => {
        this.__exportStudy(studyData);
      }, this);
      return exportButton;
    },

    __getDeleteStudyMenuButton: function(studyData) {
      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => {
        const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
        if (preferencesSettings.getConfirmDeleteStudy()) {
          const win = this.__createConfirmWindow([studyData.name]);
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__deleteStudy(studyData);
            }
          }, this);
        } else {
          this.__deleteStudy(studyData);
        }
      }, this);
      return deleteButton;
    },

    __getStudyData: function(id) {
      return this.__studies.find(study => study.uuid === id);
    },

    __itemClicked: function(item, isShiftPressed) {
      const studiesCont = this._resourcesContainer;

      if (isShiftPressed) {
        const lastIdx = studiesCont.getLastSelectedIndex();
        const currentIdx = studiesCont.getIndex(item);
        const minMaxIdx = [lastIdx, currentIdx].sort();
        for (let i=minMaxIdx[0]; i<=minMaxIdx[1]; i++) {
          const button = studiesCont.getChildren()[i];
          if (button.isVisible()) {
            button.setValue(true);
          }
        }
      }
      studiesCont.setLastSelectedIndex(studiesCont.getIndex(item));

      if (!item.isMultiSelectionMode()) {
        const studyData = this.__getStudyData(item.getUuid(), false);
        this.__startStudy(studyData);
      }
    },

    __createDuplicateCard: function(studyName) {
      const isGrid = this._resourcesContainer.getMode() === "grid";
      const duplicatingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      duplicatingStudyCard.buildLayout(
        this.tr("Duplicating ") + studyName,
        osparc.component.task.Duplicate.ICON + (isGrid ? "60" : "24"),
        null,
        true
      );
      duplicatingStudyCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addAt(duplicatingStudyCard, 1);
      return duplicatingStudyCard;
    },

    __attachDuplicateEventHandler: function(task, taskUI, studyCard) {
      const finished = (msg, msgLevel) => {
        if (msg) {
          osparc.component.message.FlashMessenger.logAs(msg, msgLevel);
        }
        taskUI.stop();
        this._resourcesContainer.remove(studyCard);
      };

      task.addListener("taskAborted", () => {
        const msg = this.tr("Duplication cancelled");
        finished(msg, "INFO");
      });
      task.addListener("resultReceived", e => {
        finished();
        const duplicatedStudyData = e.getData();
        this.reloadStudy(duplicatedStudyData["uuid"]);
      });
      task.addListener("pollingError", e => {
        const errMsg = e.getData();
        const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
        finished(msg, "ERROR");
      });
    },

    taskDuplicateReceived: function(task, studyName) {
      const duplicateTaskUI = new osparc.component.task.Duplicate(studyName);
      duplicateTaskUI.setTask(task);
      duplicateTaskUI.start();
      const duplicatingStudyCard = this.__createDuplicateCard(studyName);
      duplicatingStudyCard.setTask(task);
      this.__attachDuplicateEventHandler(task, duplicateTaskUI, duplicatingStudyCard);
    },

    _taskDataReceived: function(taskData) {
      // a bit hacky
      if (taskData["task_id"].includes("from_study") && !taskData["task_id"].includes("as_template")) {
        const interval = 1000;
        const pollTasks = osparc.data.PollTasks.getInstance();
        const task = pollTasks.addTask(taskData, interval);
        if (task === null) {
          return;
        }
        // ask backend for studyData?
        const studyName = "";
        this.taskDuplicateReceived(task, studyName);
      }
    },

    __duplicateStudy: function(studyData) {
      const text = this.tr("Duplicate process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const params = {
        url: {
          "studyId": studyData["uuid"]
        }
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "duplicate", params);
      const interval = 1000;
      const pollTasks = osparc.data.PollTasks.getInstance();
      pollTasks.createPollingTask(fetchPromise, interval)
        .then(task => this.taskDuplicateReceived(task, studyData["name"]))
        .catch(errMsg => {
          const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __exportStudy: function(studyData) {
      const exportTask = new osparc.component.task.Export(studyData);
      exportTask.start();
      exportTask.setSubtitle(this.tr("Preparing files"));
      const text = this.tr("Exporting process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const url = window.location.href + "v0/projects/" + studyData["uuid"] + ":xport";
      const downloadStartedCB = () => {
        const textSuccess = this.tr("Download started");
        exportTask.setSubtitle(textSuccess);
      };
      osparc.utils.Utils.downloadLink(url, "POST", null, downloadStartedCB)
        .catch(e => {
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(e.response)) || this.tr("Something went wrong Exporting the study");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        })
        .finally(() => {
          exportTask.stop();
        });
    },

    __importStudy: function(file) {
      const importTask = new osparc.component.task.Import();
      importTask.start();
      const text = this.tr("Importing process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const uploadingLabel = this.tr("Uploading file");
      const isGrid = this._resourcesContainer.getMode() === "grid";
      const importingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      importingStudyCard.buildLayout(
        this.tr("Importing Study..."),
        "@FontAwesome5Solid/cloud-upload-alt/" + (isGrid ? "60" : "24"),
        uploadingLabel,
        true
      );
      importingStudyCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addAt(importingStudyCard, 1);
      importTask.setSubtitle(uploadingLabel);

      const body = new FormData();
      body.append("fileName", file);

      const req = new XMLHttpRequest();
      req.upload.addEventListener("progress", ep => {
        // updateProgress
        if (ep.lengthComputable) {
          const percentComplete = ep.loaded / ep.total * 100;
          importingStudyCard.getChildControl("progress-bar").setValue(percentComplete);
          if (percentComplete === 100) {
            const processinglabel = this.tr("Processing study");
            importingStudyCard.getChildControl("state-label").setValue(processinglabel);
            importTask.setSubtitle(processinglabel);
            importingStudyCard.getChildControl("progress-bar").exclude();
          }
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      req.addEventListener("load", e => {
        // transferComplete
        if (req.status == 200) {
          const processinglabel = this.tr("Processing study");
          importingStudyCard.getChildControl("state-label").setValue(processinglabel);
          importTask.setSubtitle(processinglabel);
          importingStudyCard.getChildControl("progress-bar").exclude();
          const data = JSON.parse(req.responseText);
          const params = {
            url: {
              "studyId": data["data"]["uuid"]
            }
          };
          osparc.data.Resources.getOne("studies", params)
            .then(studyData => {
              this._resetStudyItem(studyData);
            })
            .catch(err => {
              console.log(err);
              const msg = this.tr("Something went wrong Fetching the study");
              osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
            })
            .finally(() => {
              importTask.stop();
              this._resourcesContainer.remove(importingStudyCard);
            });
        } else if (req.status == 400) {
          importTask.stop();
          this._resourcesContainer.remove(importingStudyCard);
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(req.response)) || this.tr("Something went wrong Importing the study");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        }
      });
      req.addEventListener("error", e => {
        // transferFailed
        importTask.stop();
        this._resourcesContainer.remove(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
      });
      req.addEventListener("abort", e => {
        // transferAborted
        importTask.stop();
        this._resourcesContainer.remove(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
      });
      req.open("POST", "/v0/projects:import", true);
      req.send(body);
    },

    __deleteStudy: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        // remove collaborator
        osparc.component.permissions.Study.removeCollaborator(studyData, myGid);
        const params = {
          url: {
            "studyId": studyData.uuid
          }
        };
        params["data"] = studyData;
        operationPromise = osparc.data.Resources.fetch("studies", "put", params);
      } else {
        // delete study
        operationPromise = osparc.store.Store.getInstance().deleteStudy(studyData.uuid);
      }
      operationPromise
        .then(() => {
          this.__removeFromStudyList(studyData.uuid, false);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(this.resetSelection());
    },

    __deleteStudies: function(studiesData) {
      studiesData.forEach(studyData => {
        this.__deleteStudy(studyData);
      });
    },

    __createConfirmWindow: function(studyNames) {
      const rUSure = this.tr("Are you sure you want to delete ");
      const msg = studyNames.length > 1 ? rUSure + studyNames.length + this.tr(" studies?") : rUSure + "<b>" + studyNames[0] + "</b>?";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      osparc.utils.Utils.setIdToWidget(confirmationWin.getConfirmButton(), "confirmDeleteStudyBtn");
      return confirmationWin;
    }
  }
});
