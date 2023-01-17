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
      "simcore/services/dynamic/sim4life-lite": {
        title: "Start Sim4Life Lite",
        decription: "New s4l-lite project",
        idToWidget: "startS4LButton"
      }
    }
  },

  events: {
    "publishTemplate": "qx.event.type.Data"
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
    // overridden
    initResources: function() {
      this._resourcesList = [];
      const preResourcePromises = [];
      const store = osparc.store.Store.getInstance();
      preResourcePromises.push(store.getVisibleMembers());
      preResourcePromises.push(store.getAllServices());
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        preResourcePromises.push(osparc.data.Resources.get("tags"));
      }
      preResourcePromises.push(this.__getActiveStudy());
      Promise.all(preResourcePromises)
        .then(() => {
          this.getChildControl("resources-layout");
          this.__attachEventHandlers();
          // set by the url or active study
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            this.__startStudyById(loadStudyId);
          } else {
            this.reloadResources();
          }
          // "Starting..." page
          this._hideLoadingPage();
        })
        .catch(console.error);
    },

    __getActiveStudy: function() {
      return new Promise(resolve => {
        const params = {
          url: {
            tabId: osparc.utils.Utils.getClientSessionID()
          }
        };
        osparc.data.Resources.fetch("studies", "getActive", params)
          .then(studyData => {
            if (studyData) {
              osparc.store.Store.getInstance().setCurrentStudyId(studyData["uuid"]);
              resolve(studyData["uuid"]);
            } else {
              resolve(null);
            }
          })
          .catch(err => console.error(err));
      });
    },

    reloadResources: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.user.read")) {
        this.__reloadStudies();
      } else {
        this.__setResourcesToList([]);
      }
    },

    __reloadStudies: function() {
      if (this._loadingResourcesBtn.isFetching()) {
        return;
      }
      osparc.data.Resources.get("tasks")
        .then(tasks => {
          if (tasks && tasks.length) {
            this.__tasksReceived(tasks);
          }
        });
      this._loadingResourcesBtn.setFetching(true);
      const request = this.__getNextRequest();
      request
        .then(resp => {
          const resources = resp["data"];
          this._resourcesContainer.getFlatList().nextRequest = resp["_links"]["next"];
          this.__addResourcesToList(resources);

          const nStudies = "_meta" in resp ? resp["_meta"]["total"] : 0;
          // Show "Contact Us" message if studies.length === 0 && templates.length === 0 && services.length === 0
          // Most probably is a product-stranger user (it can also be that the catalog is down)
          if (nStudies === 0) {
            const store = osparc.store.Store.getInstance();
            Promise.all([
              store.getTemplates(),
              store.getAllServices()
            ]).then(values => {
              const templates = values[0];
              const services = values[1];
              if (templates.length === 0 && Object.keys(services).length === 0) {
                const noAccessText = new qx.ui.basic.Label().set({
                  selectable: true,
                  rich: true,
                  font: "title-16",
                  paddingTop: 20
                });
                let msg = this.tr("It seems you don't have access to this product.");
                msg += "</br>";
                msg += "</br>";
                msg += this.tr("Please, contact us:");
                msg += "</br>";
                osparc.store.VendorInfo.getInstance().getSupportEmail()
                  .then(supportEmail => {
                    noAccessText.setValue(msg + supportEmail);
                  });
                this._addAt(noAccessText, 2);
              }
            });
          }

          // Show Quick Start if studies.length === 0
          const tutorial = osparc.component.tutorial.Utils.getTutorial();
          if (tutorial) {
            const dontShow = osparc.utils.Utils.localCache.getLocalStorageItem(tutorial.localStorageStr);
            if (dontShow === "true") {
              return;
            }
            if (nStudies === 0) {
              const tutorialWindow = tutorial.tutorial();
              tutorialWindow.center();
              tutorialWindow.open();
            }
          }
        })
        .catch(err => {
          console.error(err);
        })
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __setResourcesToList: function(studiesList) {
      studiesList.forEach(study => study["resourceType"] = "study");
      this._resourcesList = studiesList;
      osparc.dashboard.ResourceBrowserBase.sortStudyList(this._resourcesList);
      this._reloadCards();
    },

    __addResourcesToList: function(studiesList) {
      studiesList.forEach(study => study["resourceType"] = "study");
      studiesList.forEach(study => {
        const idx = this._resourcesList.findIndex(std => std["uuid"] === study["uuid"]);
        if (idx === -1) {
          this._resourcesList.push(study);
        }
      });
      osparc.dashboard.ResourceBrowserBase.sortStudyList(this._resourcesList);
      this._reloadNewCards();
    },

    _reloadCards: function() {
      const fetching = this._loadingResourcesBtn ? this._loadingResourcesBtn.getFetching() : false;
      const visibility = this._loadingResourcesBtn ? this._loadingResourcesBtn.getVisibility() : "excluded";

      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("studiesList");
      this.__configureCards(cards);

      this.__addNewStudyButtons();

      const loadMoreBtn = this.__createLoadMoreButton();
      loadMoreBtn.set({
        fetching,
        visibility
      });
      loadMoreBtn.addListener("appear", () => this._moreResourcesRequired());
      this._resourcesContainer.addNonResourceCard(loadMoreBtn);

      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    _reloadNewCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadNewCards();
      this.__configureCards(cards);

      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __configureCards: function(cards) {
      cards.forEach(card => {
        card.setMultiSelectionMode(this.getMultiSelection());
        card.addListener("tap", e => {
          if (!card.isLocked()) {
            this.__itemClicked(card, e.getNativeEvent().shiftKey);
          }
        }, this);
        card.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));
        this._populateCardMenu(card);
      });
    },

    __itemClicked: function(item, isShiftPressed) {
      const studiesCont = this._resourcesContainer.getFlatList();

      if (isShiftPressed) {
        const lastIdx = studiesCont.getLastSelectedIndex();
        const currentIdx = studiesCont.getIndex(item);
        const minMax = [Math.min(lastIdx, currentIdx), Math.max(lastIdx, currentIdx)];
        for (let i=minMax[0]; i<=minMax[1]; i++) {
          const card = studiesCont.getChildren()[i];
          if (card.isVisible()) {
            card.setValue(true);
          }
        }
      }
      studiesCont.setLastSelectedIndex(studiesCont.getIndex(item));

      if (!item.isMultiSelectionMode()) {
        const studyData = this.__getStudyData(item.getUuid(), false);
        this.__startStudyById(studyData["uuid"]);
      }
    },

    __startStudyById: function(studyId) {
      if (!this._checkLoggedIn()) {
        return;
      }

      this.fireDataEvent("startStudy", studyId);
    },

    __attachEventHandlers: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      const slotName = "projectStateUpdated";
      socket.on(slotName, jsonString => {
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

    reloadStudy: function(studyId) {
      const params = {
        url: {
          "studyId": studyId
        }
      };
      return osparc.data.Resources.getOne("studies", params)
        .then(studyData => this._updateStudyData(studyData))
        .catch(err => console.error(err));
    },

    __getNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES
        }
      };
      if ("nextRequest" in this._resourcesContainer.getFlatList() &&
        this._resourcesContainer.getFlatList().nextRequest !== null &&
        osparc.utils.Utils.hasParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "offset") &&
        osparc.utils.Utils.hasParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "limit")) {
        params.url.offset = osparc.utils.Utils.getParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "offset");
        params.url.limit = osparc.utils.Utils.getParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "limit");
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("studies", "getPage", params, undefined, options);
    },

    invalidateStudies: function() {
      osparc.store.Store.getInstance().invalidate("studies");
      this.__setResourcesToList([]);
      this._resourcesContainer.getFlatList().nextRequest = null;
    },

    __addNewStudyButtons: function() {
      switch (osparc.utils.Utils.getProductName()) {
        case "osparc":
          this.__addNewStudyButton();
          break;
        case "tis":
          this.__addNewPlanButton();
          break;
        case "s4l":
          this.__addNewS4LServiceButtons();
          break;
        case "s4llite":
          this.__addNewS4LLiteServiceButtons();
          break;
      }
    },

    __addNewStudyButton: function() {
      const mode = this._resourcesContainer.getMode();
      const newStudyBtn = (mode === "grid") ? new osparc.dashboard.GridButtonNew() : new osparc.dashboard.ListButtonNew();
      newStudyBtn.setCardKey("new-study");
      newStudyBtn.subscribeToFilterGroup("searchBarFilter");
      osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
      newStudyBtn.addListener("execute", () => this.__newStudyBtnClicked(newStudyBtn));
      if (this._resourcesContainer.getMode() === "list") {
        const width = this._resourcesContainer.getBounds().width - 15;
        newStudyBtn.setWidth(width);
      }
      this._resourcesContainer.addNonResourceCard(newStudyBtn);
    },

    __addNewPlanButton: function() {
      const mode = this._resourcesContainer.getMode();
      osparc.data.Resources.get("templates")
        .then(templates => {
          // replace if a "TI Planning Tool" template exists
          const templateData = templates.find(t => t.name === this.self().EXPECTED_TI_TEMPLATE_TITLE);
          if (templateData) {
            const title = this.tr("New Plan");
            const desc = this.tr("Start a new plan");
            const newPlanButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
            newPlanButton.setCardKey("new-plan");
            osparc.utils.Utils.setIdToWidget(newPlanButton, "newPlanButton");
            newPlanButton.addListener("execute", () => this.__newPlanBtnClicked(newPlanButton, templateData));
            if (this._resourcesContainer.getMode() === "list") {
              const width = this._resourcesContainer.getBounds().width - 15;
              newPlanButton.setWidth(width);
            }
            this._resourcesContainer.addNonResourceCard(newPlanButton);
          }
        });
    },

    __addNewStudyFromServiceButtons: function(services, serviceKey, newButtonInfo) {
      const mode = this._resourcesContainer.getMode();
      // Make sure we have access to that service
      const versions = osparc.utils.Services.getVersions(services, serviceKey);
      if (versions.length && newButtonInfo) {
        const title = newButtonInfo.title;
        const desc = newButtonInfo.decription;
        const newStudyFromServiceButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
        newStudyFromServiceButton.setCardKey("new-"+serviceKey);
        osparc.utils.Utils.setIdToWidget(newStudyFromServiceButton, newButtonInfo.idToWidget);
        newStudyFromServiceButton.addListener("execute", () => this.__newStudyFromServiceBtnClicked(newStudyFromServiceButton, serviceKey, versions[versions.length-1]));
        if (this._resourcesContainer.getMode() === "list") {
          const width = this._resourcesContainer.getBounds().width - 15;
          newStudyFromServiceButton.setWidth(width);
        }
        this._resourcesContainer.addNonResourceCard(newStudyFromServiceButton);
      }
    },

    __addNewS4LServiceButtons: function() {
      const store = osparc.store.Store.getInstance();
      store.getAllServices()
        .then(services => {
          // add new plus buttons if key services exists
          const newButtonsInfo = this.self().EXPECTED_S4L_SERVICE_KEYS;
          Object.keys(newButtonsInfo).forEach(serviceKey => {
            this.__addNewStudyFromServiceButtons(services, serviceKey, newButtonsInfo[serviceKey]);
          });
        });
    },

    __addNewS4LLiteServiceButtons: function() {
      const store = osparc.store.Store.getInstance();
      store.getAllServices()
        .then(services => {
          // add new plus buttons if key services exists
          const newButtonsInfo = this.self().EXPECTED_S4L_LIGHT_SERVICE_KEYS;
          Object.keys(newButtonsInfo).forEach(serviceKey => {
            this.__addNewStudyFromServiceButtons(services, serviceKey, newButtonsInfo[serviceKey]);
          });
        });
    },

    // LAYOUT //
    _createLayout: function() {
      this._createResourcesLayout("study");
      const list = this._resourcesContainer.getFlatList();
      if (list) {
        osparc.utils.Utils.setIdToWidget(list, "studiesList");
      }

      const importStudyButton = this.__createImportButton();
      this._secondaryBar.add(importStudyButton);
      importStudyButton.exclude();
      osparc.utils.DisabledPlugins.isImportDisabled()
        .then(isDisabled => {
          importStudyButton.setVisibility(isDisabled ? "excluded" : "visible");
        });

      const selectStudiesButton = this.__createSelectButton();
      this._secondaryBar.add(selectStudiesButton);

      const studiesDeleteButton = this.__createDeleteButton(false);
      this._secondaryBar.add(studiesDeleteButton);

      this._secondaryBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this._addViewModeButton();


      this.__addNewStudyButtons();

      const loadMoreBtn = this.__createLoadMoreButton();
      this._resourcesContainer.addNonResourceCard(loadMoreBtn);

      this.addListener("changeMultiSelection", e => {
        const multiEnabled = e.getData();
        const cards = this._resourcesContainer.getCards();
        cards.forEach(card => {
          if (!osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)) {
            card.setEnabled(!multiEnabled);
          }
        });
        importStudyButton.setEnabled(!multiEnabled);
      });

      this._resourcesContainer.addListener("changeSelection", e => {
        const selection = e.getData();
        studiesDeleteButton.set({
          visibility: selection.length ? "visible" : "excluded",
          label: selection.length > 1 ? this.tr("Delete selected")+" ("+selection.length+")" : this.tr("Delete")
        });
      });

      this._resourcesContainer.addListener("changeVisibility", () => this._moreResourcesRequired());

      return this._resourcesContainer;
    },

    __createLoadMoreButton: function() {
      const mode = this._resourcesContainer.getMode();
      const loadMoreBtn = this._loadingResourcesBtn = (mode === "grid") ? new osparc.dashboard.GridButtonLoadMore() : new osparc.dashboard.ListButtonLoadMore();
      loadMoreBtn.setCardKey("load-more");
      osparc.utils.Utils.setIdToWidget(loadMoreBtn, "studiesLoading");
      loadMoreBtn.addListener("execute", () => {
        loadMoreBtn.setValue(false);
        this._moreResourcesRequired();
      });
      return loadMoreBtn;
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
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        visibility: "excluded"
      });
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
      this._resourcesContainer.getCards().forEach(studyItem => {
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(studyItem)) {
          studyItem.setMultiSelectionMode(value);
          if (value === false) {
            studyItem.setValue(false);
          }
        }
      });
    },
    // LAYOUT //

    __studyStateReceived: function(studyId, state, errors) {
      osparc.store.Store.getInstance().setStudyState(studyId, state);
      const idx = this._resourcesList.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this._resourcesList[idx]["state"] = state;
      }
      const studyItem = this._resourcesContainer.getCards().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === studyId);
      if (studyItem) {
        studyItem.setState(state);
      }
      if (errors.length) {
        console.error(errors);
      }
    },

    __newStudyBtnClicked: function(button) {
      button.setValue(false);
      const minStudyData = osparc.data.model.Study.createMyNewStudyObject();
      const title = osparc.utils.Utils.getUniqueStudyName(minStudyData.name, this._resourcesList);
      minStudyData["name"] = title;
      minStudyData["description"] = "";
      this.__createStudy(minStudyData, null);
    },

    __newPlanBtnClicked: function(button, templateData) {
      button.setValue(false);
      const title = osparc.utils.Utils.getUniqueStudyName(templateData.name, this._resourcesList);
      templateData.name = title;
      this._showLoadingPage(this.tr("Creating ") + (templateData.name || this.tr("Study")));
      osparc.utils.Study.createStudyFromTemplate(templateData, this._loadingPage)
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

    __newStudyFromServiceBtnClicked: function(button, key, version) {
      button.setValue(false);
      this._showLoadingPage(this.tr("Creating Study"));
      osparc.utils.Study.createStudyFromService(key, version, this._resourcesList)
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
          this.__startStudyById(studyData["uuid"]);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    _updateStudyData: function(studyData) {
      studyData["resourceType"] = "study";
      const studies = this._resourcesList;
      const index = studies.findIndex(study => study["uuid"] === studyData["uuid"]);
      if (index === -1) {
        studies.push(studyData);
      } else {
        studies[index] = studyData;
      }
      this._reloadCards();
    },

    __removeFromStudyList: function(studyId) {
      const idx = this._resourcesList.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this._resourcesList.splice(idx, 1);
      }
      this._resourcesContainer.removeCard(studyId);
    },

    _populateCardMenu: function(card) {
      const menu = card.getMenu();
      const studyData = card.getResourceData();

      const renameStudyButton = this.__getRenameStudyMenuButton(studyData);
      menu.add(renameStudyButton);

      const studyDataButton = this.__getStudyDataMenuButton(studyData);
      menu.add(studyDataButton);

      const shareButton = this._getShareMenuButton(card);
      menu.add(shareButton);

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
        .then(updatedStudyData => this._updateStudyData(updatedStudyData))
        .catch(err => {
          const msg = this.tr("Something went wrong updating the Service");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
          console.error(err);
        });
    },

    __getStudyDataMenuButton: function(studyData) {
      const text = osparc.utils.Utils.capitalize(osparc.utils.Utils.getStudyLabel()) + this.tr(" data...");
      const studyDataButton = new qx.ui.menu.Button(text);
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
      return this._resourcesList.find(study => study.uuid === id);
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
      return duplicatingStudyCard;
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
      const uploadingLabel = this.tr("Uploading file");
      const importTask = new osparc.component.task.Import();
      importTask.start();
      importTask.setSubtitle(uploadingLabel);

      const text = this.tr("Importing process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const isGrid = this._resourcesContainer.getMode() === "grid";
      const importingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      importingStudyCard.buildLayout(
        this.tr("Importing Study..."),
        "@FontAwesome5Solid/cloud-upload-alt/" + (isGrid ? "60" : "24"),
        uploadingLabel,
        true
      );
      importingStudyCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addNonResourceCard(importingStudyCard);

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
            .then(studyData => this._updateStudyData(studyData))
            .catch(err => {
              console.error(err);
              const msg = this.tr("Something went wrong Fetching the study");
              osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
            })
            .finally(() => {
              importTask.stop();
              this._resourcesContainer.removeNonResourceCard(importingStudyCard);
            });
        } else if (req.status == 400) {
          importTask.stop();
          this._resourcesContainer.removeNonResourceCard(importingStudyCard);
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(req.response)) || this.tr("Something went wrong Importing the study");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        }
      });
      req.addEventListener("error", e => {
        // transferFailed
        importTask.stop();
        this._resourcesContainer.removeNonResourceCard(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
      });
      req.addEventListener("abort", e => {
        // transferAborted
        importTask.stop();
        this._resourcesContainer.removeNonResourceCard(importingStudyCard);
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
        .then(() => this.__removeFromStudyList(studyData.uuid, false))
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(() => {
          this.resetSelection();
        });
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
    },

    // TASKS //
    __tasksReceived: function(tasks) {
      tasks.forEach(taskData => this._taskDataReceived(taskData));
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

    taskDuplicateReceived: function(task, studyName) {
      const duplicateTaskUI = new osparc.component.task.Duplicate(studyName);
      duplicateTaskUI.setTask(task);
      duplicateTaskUI.start();
      const duplicatingStudyCard = this.__createDuplicateCard(studyName);
      duplicatingStudyCard.setTask(task);
      duplicatingStudyCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addNonResourceCard(duplicatingStudyCard);
      this.__attachDuplicateEventHandler(task, duplicateTaskUI, duplicatingStudyCard);
    },

    __attachDuplicateEventHandler: function(task, taskUI, duplicatingStudyCard) {
      const finished = (msg, msgLevel) => {
        if (msg) {
          osparc.component.message.FlashMessenger.logAs(msg, msgLevel);
        }
        taskUI.stop();
        this._resourcesContainer.removeNonResourceCard(duplicatingStudyCard);
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
    }
    // TASKS //
  }
});
