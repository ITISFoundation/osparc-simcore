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
 * @asset(osparc/new_studies.json")
 */

/**
 * Widget that shows lists user's studies.
 *
 * It is the entry point to start editing or creating a new study.
 *
 * Also takes care of retrieving the list of services and pushing the changes in the metadata.
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

  construct: function() {
    this._resourceType = "study";
    this.base(arguments);
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
    },
    // Ordering by Possibilities:
    // field: type | uuid | name | description | prj_owner | creation_date | last_change_date
    // direction: asc | desc
    orderBy: {
      check: "Object",
      init: {
        field: "last_change_date",
        direction: "desc"
      }
    }
  },

  members: {
    // overridden
    initResources: function() {
      this._resourcesList = [];
      this.__getActiveStudy()
        .then(() => {
          this.getChildControl("resources-layout");
          this.__attachEventHandlers();
          // set by the url or active study
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            const cancelCB = () => this.reloadResources();
            const isStudyCreation = false;
            this._startStudyById(loadStudyId, null, cancelCB, isStudyCreation);
          } else {
            this.reloadResources();
          }
          // "Starting..." page
          this._hideLoadingPage();
        })
        .catch(console.error);
    },

    __getActiveStudy: function() {
      const params = {
        url: {
          tabId: osparc.utils.Utils.getClientSessionID()
        }
      };
      return osparc.data.Resources.fetch("studies", "getActive", params)
        .then(studyData => {
          if (studyData) {
            osparc.store.Store.getInstance().setCurrentStudyId(studyData["uuid"]);
          }
        })
        .catch(err => console.error(err));
    },

    reloadResources: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.user.read")) {
        this.__reloadStudies();
      } else {
        this.__resetStudiesList();
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
      this._loadingResourcesBtn.setVisibility("visible");
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
                  font: "text-18",
                  paddingTop: 20
                });
                let msg = this.tr("It seems you don't have access to this product.");
                msg += "</br>";
                msg += "</br>";
                msg += this.tr("Please contact us:");
                msg += "</br>";
                const supportEmail = osparc.store.VendorInfo.getInstance().getSupportEmail();
                noAccessText.setValue(msg + supportEmail);
                this._addAt(noAccessText, 2);
              }
            });
          }

          // Show Quick Start if studies.length === 0
          const quickStart = osparc.product.quickStart.Utils.getQuickStart();
          if (quickStart) {
            const dontShow = osparc.utils.Utils.localCache.getLocalStorageItem(quickStart.localStorageStr);
            if (dontShow === "true") {
              return;
            }
            if (nStudies === 0) {
              const tutorialWindow = quickStart.tutorial();
              tutorialWindow.center();
              tutorialWindow.open();
            }
          }
        })
        .catch(err => console.error(err))
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __reloadFilteredStudies: function(text) {
      if (this._loadingResourcesBtn.isFetching()) {
        return;
      }
      this.__resetStudiesList();
      this._loadingResourcesBtn.setFetching(true);
      this._loadingResourcesBtn.setVisibility("visible");
      const request = this.__getTextFilteredNextRequest(text);
      request
        .then(resp => {
          console.log("filteredStudies", resp);
          const filteredStudies = resp["data"];
          this._resourcesContainer.getFlatList().nextRequest = resp["_links"]["next"];
          this.__addResourcesToList(filteredStudies);
        })
        .catch(err => console.error(err))
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __reloadSortedByStudies: function() {
      if (this._loadingResourcesBtn.isFetching()) {
        return;
      }
      this.__resetStudiesList();
      this._loadingResourcesBtn.setFetching(true);
      this._loadingResourcesBtn.setVisibility("visible");
      const request = this.__getSortedByNextRequest();
      request
        .then(resp => {
          const sortedStudies = resp["data"];
          this._resourcesContainer.getFlatList().nextRequest = resp["_links"]["next"];
          this.__addResourcesToList(sortedStudies);
        })
        .catch(err => console.error(err))
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __resetStudiesList: function() {
      this._resourcesList = [];
      const sortByValue = this.getOrderBy().field;
      osparc.dashboard.ResourceBrowserBase.sortStudyList(this._resourcesList, sortByValue);
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
      const sortByValue = this.getOrderBy().field;
      osparc.dashboard.ResourceBrowserBase.sortStudyList(this._resourcesList, sortByValue);
      this._reloadNewCards();

      studiesList.forEach(study => {
        const state = study["state"];
        if (state && "locked" in state && state["locked"]["value"] && state["locked"]["status"] === "CLOSING") {
          // websocket might have already notified that the state was closed.
          // But the /projects calls response got after the ws message. Ask again to make sure
          const delay = 2000;
          const studyId = study["uuid"];
          setTimeout(() => {
            const params = {
              url: {
                studyId
              }
            };
            osparc.data.Resources.getOne("studies", params)
              .then(studyData => {
                this.__studyStateReceived(study["uuid"], studyData["state"]);
              });
          }, delay);
        }
      });
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

      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    _reloadNewCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadNewCards();
      this.__configureCards(cards);

      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __configureCards: function(cards) {
      cards.forEach(card => {
        card.setMultiSelectionMode(this.getMultiSelection());
        card.addListener("tap", e => {
          if (card.isLocked()) {
            card.setValue(false);
          } else {
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
        this._openResourceDetails(studyData);
        this.resetSelection();
      }
    },

    __attachEventHandlers: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      socket.on("projectStateUpdated", data => {
        if (data) {
          const studyId = data["project_uuid"];
          const state = ("data" in data) ? data.data : {};
          const errors = ("errors" in data) ? data.errors : [];
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

      qx.event.message.Bus.subscribe("reloadStudies", () => {
        this.invalidateStudies();
        this.reloadResources();
      }, this);
    },

    __getNextRequestParams: function() {
      if ("nextRequest" in this._resourcesContainer.getFlatList() &&
        this._resourcesContainer.getFlatList().nextRequest !== null &&
        osparc.utils.Utils.hasParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "offset") &&
        osparc.utils.Utils.hasParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "limit")
      ) {
        return {
          offset: osparc.utils.Utils.getParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "offset"),
          limit: osparc.utils.Utils.getParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "limit")
        };
      }
      return null;
    },

    __getNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES,
          orderBy: JSON.stringify(this.getOrderBy()),
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };

      if (params.url.orderBy) {
        return osparc.data.Resources.fetch("studies", "getPageSortBySearch", params, undefined, options);
      } else if (params.url.search) {
        return osparc.data.Resources.fetch("studies", "getPageFilterSearch", params, undefined, options);
      }
      return osparc.data.Resources.fetch("studies", "getPage", params, undefined, options);
    },

    __getTextFilteredNextRequest: function(text) {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES,
          text
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("studies", "getPageFilterSearch", params, undefined, options);
    },

    __getSortedByNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES,
          orderBy: JSON.stringify(this.getOrderBy())
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("studies", "getPageSortBySearch", params, undefined, options);
    },

    invalidateStudies: function() {
      osparc.store.Store.getInstance().invalidate("studies");
      this.__resetStudiesList();
      this._resourcesContainer.getFlatList().nextRequest = null;
    },

    __addNewStudyButtons: function() {
      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          this.__addEmptyStudyPlusButton();
          break;
        case "tis":
          this.__addTIPPlusButtons();
          break;
        case "s4l":
        case "s4lacad":
        case "s4llite":
          this.__addPlusButtonsFromServices();
          break;
      }
    },

    __addEmptyStudyPlusButton: function() {
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

    __addTIPPlusButtons: function() {
      const mode = this._resourcesContainer.getMode();
      osparc.data.Resources.get("templates")
        .then(templates => {
          if (templates) {
            osparc.utils.Utils.fetchJSON("/resource/osparc/new_studies.json")
              .then(newStudiesData => {
                const product = osparc.product.Utils.getProductName()
                if (product in newStudiesData) {
                  const newButtonsInfo = newStudiesData[product].resources;
                  const title = this.tr("New Plan");
                  const desc = this.tr("Choose Plan in pop-up");
                  const newStudyBtn = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
                  newStudyBtn.setCardKey("new-study");
                  newStudyBtn.subscribeToFilterGroup("searchBarFilter");
                  osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
                  if (this._resourcesContainer.getMode() === "list") {
                    const width = this._resourcesContainer.getBounds().width - 15;
                    newStudyBtn.setWidth(width);
                  }
                  this._resourcesContainer.addNonResourceCard(newStudyBtn);
                  newStudyBtn.addListener("execute", () => {
                    newStudyBtn.setValue(false);

                    const foundTemplates = newButtonsInfo.filter(newButtonInfo => templates.find(t => t.name === newButtonInfo.expectedTemplateLabel));
                    const groups = newStudiesData[product].categories;
                    const newStudies = new osparc.dashboard.NewStudies(foundTemplates, groups);
                    newStudies.setGroupBy("category");
                    const winTitle = this.tr("New Plan");
                    const win = osparc.ui.window.Window.popUpInWindow(newStudies, winTitle, 640, 600).set({
                      clickAwayClose: false,
                      resizable: true
                    });
                    newStudies.addListener("newStudyClicked", e => {
                      win.close();
                      const templateInfo = e.getData();
                      const templateData = templates.find(t => t.name === templateInfo.expectedTemplateLabel);
                      if (templateData) {
                        this.__newPlanBtnClicked(templateData, templateInfo.newStudyLabel);
                      }
                    });
                    osparc.utils.Utils.setIdToWidget(win, "newStudiesWindow");
                  });
                }
              });
          }
        });
    },

    __addNewStudyFromServiceButtons: function(services, serviceKey, newButtonInfo) {
      const mode = this._resourcesContainer.getMode();
      // Make sure we have access to that service
      const versions = osparc.service.Utils.getVersions(services, serviceKey);
      if (versions.length && newButtonInfo) {
        const title = newButtonInfo.title;
        const desc = newButtonInfo.description;
        const newStudyFromServiceButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
        newStudyFromServiceButton.setCardKey("new-"+serviceKey);
        osparc.utils.Utils.setIdToWidget(newStudyFromServiceButton, newButtonInfo.idToWidget);
        newStudyFromServiceButton.addListener("execute", () => this.__newStudyFromServiceBtnClicked(newStudyFromServiceButton, serviceKey, versions[versions.length-1], newButtonInfo.newStudyLabel));
        if (this._resourcesContainer.getMode() === "list") {
          const width = this._resourcesContainer.getBounds().width - 15;
          newStudyFromServiceButton.setWidth(width);
        }
        this._resourcesContainer.addNonResourceCard(newStudyFromServiceButton);
      }
    },

    __addPlusButtonsFromServices: function() {
      const store = osparc.store.Store.getInstance();
      store.getAllServices()
        .then(services => {
          // add new plus buttons if key services exists
          osparc.utils.Utils.fetchJSON("/resource/osparc/new_studies.json")
            .then(newStudiesData => {
              const product = osparc.product.Utils.getProductName()
              if (product in newStudiesData) {
                const newButtonsInfo = newStudiesData[product].resources;
                newButtonsInfo.forEach(newButtonInfo => {
                  this.__addNewStudyFromServiceButtons(services, newButtonInfo.expectedKey, newButtonInfo);
                });
              }
            });
        });
    },

    // LAYOUT //
    _createLayout: function() {
      this._createResourcesLayout();
      const list = this._resourcesContainer.getFlatList();
      if (list) {
        osparc.utils.Utils.setIdToWidget(list, "studiesList");
      }

      const importStudyButton = this.__createImportButton();
      const isDisabled = osparc.utils.DisabledPlugins.isImportDisabled();
      importStudyButton.setVisibility(isDisabled ? "excluded" : "visible");
      this._toolbar.add(importStudyButton);

      const selectStudiesButton = this.__createSelectButton();
      this._toolbar.add(selectStudiesButton);

      const studiesDeleteButton = this.__createDeleteButton(false);
      this._toolbar.add(studiesDeleteButton);

      this._toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.__addSortByButton();
      this._addViewModeButton();

      this._addResourceFilter();

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
          appearance: "danger-button",
          visibility: selection.length ? "visible" : "excluded",
          label: selection.length > 1 ? this.tr("Delete selected")+" ("+selection.length+")" : this.tr("Delete")
        });
      });

      this._resourcesContainer.addListener("changeVisibility", () => this._moreResourcesRequired());

      return this._resourcesContainer;
    },

    __addSortByButton: function() {
      const sortByButton = new osparc.dashboard.SortedByMenuButton();
      sortByButton.set({
        appearance: "form-button-outlined"
      });
      osparc.utils.Utils.setIdToWidget(sortByButton, "sortByButton");
      sortByButton.addListener("sortByChanged", e => {
        this.setOrderBy(e.getData())
        this.__reloadSortedByStudies();
      }, this);
      this._toolbar.add(sortByButton);
    },

    __addShowSharedWithButton: function() {
      const sharedWithButton = new osparc.dashboard.SharedWithMenuButton("study");
      sharedWithButton.set({
        appearance: "form-button-outlined"
      });
      osparc.utils.Utils.setIdToWidget(sharedWithButton, "sharedWithButton");

      sharedWithButton.addListener("sharedWith", e => {
        const option = e.getData();
        this._searchBarFilter.setSharedWithActiveFilter(option.id, option.label);
      }, this);
      this._searchBarFilter.addListener("filterChanged", e => {
        const filterData = e.getData();
        if (filterData.text) {
          this.__reloadFilteredStudies(filterData.text);
        } else {
          this.__reloadStudies();
        }
        sharedWithButton.filterChanged(filterData);
      }, this);

      this._toolbar.add(sharedWithButton);
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
      importButton.set({
        appearance: "form-button-outlined"
      });
      importButton.addListener("execute", () => {
        const importStudy = new osparc.study.Import();
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
          const maxSize = 10 * 1000 * 1000 * 1000; // 10 GB
          if (size > maxSize) {
            osparc.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
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
        const preferencesSettings = osparc.Preferences.getInstance();
        if (preferencesSettings.getConfirmDeleteStudy()) {
          const win = this.__createConfirmWindow(selection.map(button => button.getTitle()));
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__doDeleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
            }
          }, this);
        } else {
          this.__doDeleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
        }
      }, this);
      return deleteButton;
    },

    __createSelectButton: function() {
      const selectButton = new qx.ui.form.ToggleButton().set({
        appearance: "form-button-outlined",
        marginRight: 8
      });
      selectButton.bind("value", this, "multiSelection");
      selectButton.bind("value", selectButton, "label", {
        converter: val => val ? this.tr("Cancel Selection") : (this.tr("Select ") + osparc.product.Utils.getStudyAlias({
          plural: true,
          firstUpperCase: true
        }))
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
      if (errors && errors.length) {
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

    __newPlanBtnClicked: function(templateData, newStudyName) {
      // do not override cached template data
      const templateCopyData = osparc.utils.Utils.deepCloneObject(templateData);
      const title = osparc.utils.Utils.getUniqueStudyName(newStudyName, this._resourcesList);
      templateCopyData.name = title;
      this._showLoadingPage(this.tr("Creating ") + (newStudyName || osparc.product.Utils.getStudyAlias()));
      osparc.study.Utils.createStudyFromTemplate(templateCopyData, this._loadingPage)
        .then(studyId => {
          const openCB = () => this._hideLoadingPage();
          const cancelCB = () => {
            this._hideLoadingPage();
            const params = {
              url: {
                "studyId": studyId
              }
            };
            osparc.data.Resources.fetch("studies", "delete", params, studyId);
          };
          const isStudyCreation = true;
          this._startStudyById(studyId, openCB, cancelCB, isStudyCreation);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __newStudyFromServiceBtnClicked: function(button, key, version, newStudyLabel) {
      button.setValue(false);
      this._showLoadingPage(this.tr("Creating ") + osparc.product.Utils.getStudyAlias());
      osparc.study.Utils.createStudyFromService(key, version, this._resourcesList, newStudyLabel)
        .then(studyId => {
          const openCB = () => this._hideLoadingPage();
          const cancelCB = () => {
            this._hideLoadingPage();
            const params = {
              url: {
                "studyId": studyId
              }
            };
            osparc.data.Resources.fetch("studies", "delete", params, studyId);
          };
          const isStudyCreation = true;
          this._startStudyById(studyId, openCB, cancelCB, isStudyCreation);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __createStudy: function(minStudyData) {
      this._showLoadingPage(this.tr("Creating ") + (minStudyData.name || osparc.product.Utils.getStudyAlias()));

      const params = {
        data: minStudyData
      };
      osparc.study.Utils.createStudyAndPoll(params)
        .then(studyData => {
          const openCB = () => this._hideLoadingPage();
          const cancelCB = () => {
            this._hideLoadingPage();
            const params2 = {
              url: {
                "studyId": studyData["uuid"]
              }
            };
            osparc.data.Resources.fetch("studies", "delete", params2, studyData["uuid"]);
          };
          const isStudyCreation = true;
          this._startStudyById(studyData["uuid"], openCB, cancelCB, isStudyCreation);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    _updateStudyData: function(studyData) {
      studyData["resourceType"] = "study";
      const studies = this._resourcesList;
      const index = studies.findIndex(study => study["uuid"] === studyData["uuid"]);
      if (index === -1) {
        // add it in first position, most likely it's a new study
        studies.unshift(studyData);
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

      const writeAccess = osparc.data.model.Study.canIWrite(studyData["accessRights"]);
      const deleteAccess = osparc.data.model.Study.canIDelete(studyData["accessRights"]);

      const openButton = this._getOpenMenuButton(studyData);
      if (openButton) {
        menu.add(openButton);
      }

      if (writeAccess) {
        const renameStudyButton = this.__getRenameStudyMenuButton(studyData);
        menu.add(renameStudyButton);
      }

      if (writeAccess) {
        const editThumbnailButton = this.__getThumbnailStudyMenuButton(studyData);
        menu.add(editThumbnailButton);
      }

      const duplicateStudyButton = this.__getDuplicateMenuButton(studyData);
      menu.add(duplicateStudyButton);

      if (osparc.product.Utils.isProduct("osparc")) {
        const exportStudyButton = this.__getExportMenuButton(studyData);
        menu.add(exportStudyButton);
      }

      menu.addSeparator();

      if (writeAccess) {
        const shareButton = this._getShareMenuButton(card);
        if (shareButton) {
          menu.add(shareButton);
        }

        const tagsButton = this._getTagsMenuButton(card);
        if (tagsButton) {
          menu.add(tagsButton);
        }
      }

      const studyDataButton = this.__getStudyDataMenuButton(card);
      menu.add(studyDataButton);

      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const billingsSettingsButton = this.__getBillingMenuButton(card);
        menu.add(billingsSettingsButton);
      }

      if (deleteAccess) {
        const deleteButton = this.__getDeleteStudyMenuButton(studyData, false);
        if (deleteButton) {
          menu.addSeparator();
          menu.add(deleteButton);
        }
      }
    },

    __getRenameStudyMenuButton: function(studyData) {
      const renameButton = new qx.ui.menu.Button(this.tr("Rename..."));
      renameButton.addListener("execute", () => {
        const renamer = new osparc.widget.Renamer(studyData["name"]);
        renamer.addListener("labelChanged", e => {
          renamer.close();
          const newLabel = e.getData()["newLabel"];
          this.__updateName(studyData, newLabel);
        }, this);
        renamer.center();
        renamer.open();
      }, this);
      return renameButton;
    },

    __getThumbnailStudyMenuButton: function(studyData) {
      const thumbButton = new qx.ui.menu.Button(this.tr("Thumbnail..."));
      thumbButton.addListener("execute", () => {
        const title = this.tr("Edit Thumbnail");
        const oldThumbnail = studyData.thumbnail;
        const suggestions = osparc.editor.ThumbnailSuggestions.extractThumbnailSuggestions(studyData);
        const thumbnailEditor = new osparc.editor.ThumbnailEditor(oldThumbnail, suggestions);
        const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, suggestions.length > 2 ? 500 : 350, 280);
        thumbnailEditor.addListener("updateThumbnail", e => {
          win.close();
          const newUrl = e.getData();
          this.__updateThumbnail(studyData, newUrl);
        }, this);
        thumbnailEditor.addListener("cancel", () => win.close());
      }, this);
      return thumbButton;
    },

    __updateName: function(studyData, name) {
      osparc.info.StudyUtils.patchStudyData(studyData, "name", name)
        .then(() => this._updateStudyData(studyData))
        .catch(err => {
          console.error(err);
          const msg = this.tr("Something went wrong Renaming");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __updateThumbnail: function(studyData, url) {
      osparc.info.StudyUtils.patchStudyData(studyData, "thumbnail", url)
        .then(() => this._updateStudyData(studyData))
        .catch(err => {
          console.error(err);
          const msg = this.tr("Something went wrong updating the Thumbnail");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __getStudyDataMenuButton: function(card) {
      const text = osparc.utils.Utils.capitalize(osparc.product.Utils.getStudyAlias()) + this.tr(" files...");
      const studyDataButton = new qx.ui.menu.Button(text);
      studyDataButton.addListener("tap", () => card.openData(), this);
      return studyDataButton;
    },

    __getBillingMenuButton: function(card) {
      const text = osparc.utils.Utils.capitalize(this.tr("Billing Settings..."));
      const studyBillingSettingsButton = new qx.ui.menu.Button(text);
      studyBillingSettingsButton.addListener("tap", () => card.openBilling(), this);
      return studyBillingSettingsButton;
    },

    __getDuplicateMenuButton: function(studyData) {
      const duplicateButton = new qx.ui.menu.Button(this.tr("Duplicate"));
      duplicateButton.addListener("execute", () => this.__duplicateStudy(studyData), this);
      return duplicateButton;
    },

    __getExportMenuButton: function(studyData) {
      const exportButton = new qx.ui.menu.Button(this.tr("Export cMIS"));
      const isDisabled = osparc.utils.DisabledPlugins.isExportDisabled();
      exportButton.setVisibility(isDisabled ? "excluded" : "visible");
      exportButton.addListener("execute", () => this.__exportStudy(studyData), this);
      return exportButton;
    },

    _deleteResourceRequested: function(studyId) {
      this.__deleteStudyRequested(this.__getStudyData(studyId));
    },

    __deleteStudyRequested: function(studyData) {
      const preferencesSettings = osparc.Preferences.getInstance();
      if (preferencesSettings.getConfirmDeleteStudy()) {
        const win = this.__createConfirmWindow([studyData.name]);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__doDeleteStudy(studyData);
          }
        }, this);
      } else {
        this.__doDeleteStudy(studyData);
      }
    },

    __getDeleteStudyMenuButton: function(studyData) {
      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
      deleteButton.set({
        appearance: "menu-button"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => this.__deleteStudyRequested(studyData), this);
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
        osparc.task.Duplicate.ICON + (isGrid ? "60" : "24"),
        null,
        true
      );

      if (this._resourcesContainer.getMode() === "list") {
        const width = this._resourcesContainer.getBounds().width - 15;
        duplicatingStudyCard.setWidth(width);
      }
      return duplicatingStudyCard;
    },

    __duplicateStudy: function(studyData) {
      const text = this.tr("Duplicate process started and added to the background tasks");
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

      const params = {
        url: {
          "studyId": studyData["uuid"]
        }
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "duplicate", params, null, {"pollTask": true});
      const interval = 1000;
      const pollTasks = osparc.data.PollTasks.getInstance();
      pollTasks.createPollingTask(fetchPromise, interval)
        .then(task => this.__taskDuplicateReceived(task, studyData["name"]))
        .catch(errMsg => {
          const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __exportStudy: function(studyData) {
      const exportTask = new osparc.task.Export(studyData);
      exportTask.start();
      exportTask.setSubtitle(this.tr("Preparing files"));
      const text = this.tr("Exporting process started and added to the background tasks");
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

      const url = window.location.href + "v0/projects/" + studyData["uuid"] + ":xport";
      const progressCB = () => {
        const textSuccess = this.tr("Download started");
        exportTask.setSubtitle(textSuccess);
      };
      osparc.utils.Utils.downloadLink(url, "POST", null, progressCB)
        .catch(e => {
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(e.response)) || this.tr("Something went wrong Exporting the study");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        })
        .finally(() => {
          exportTask.stop();
        });
    },

    __importStudy: function(file) {
      const uploadingLabel = this.tr("Uploading file");
      const importTask = new osparc.task.Import();
      importTask.start();
      importTask.setSubtitle(uploadingLabel);

      const text = this.tr("Importing process started and added to the background tasks");
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

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
            const processingLabel = this.tr("Processing study");
            importingStudyCard.getChildControl("state-label").setValue(processingLabel);
            importTask.setSubtitle(processingLabel);
            importingStudyCard.getChildControl("progress-bar").exclude();
          }
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      req.addEventListener("load", e => {
        // transferComplete
        if (req.status == 200) {
          const processingLabel = this.tr("Processing study");
          importingStudyCard.getChildControl("state-label").setValue(processingLabel);
          importTask.setSubtitle(processingLabel);
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
              osparc.FlashMessenger.logAs(msg, "ERROR");
            })
            .finally(() => {
              importTask.stop();
              this._resourcesContainer.removeNonResourceCard(importingStudyCard);
            });
        } else if (req.status == 400) {
          importTask.stop();
          this._resourcesContainer.removeNonResourceCard(importingStudyCard);
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(req.response)) || this.tr("Something went wrong Importing the study");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        }
      });
      req.addEventListener("error", e => {
        // transferFailed
        importTask.stop();
        this._resourcesContainer.removeNonResourceCard(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.FlashMessenger.logAs(msg, "ERROR");
      });
      req.addEventListener("abort", e => {
        // transferAborted
        importTask.stop();
        this._resourcesContainer.removeNonResourceCard(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.FlashMessenger.logAs(msg, "ERROR");
      });
      req.open("POST", "/v0/projects:import", true);
      req.send(body);
    },

    __doDeleteStudy: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        const arCopy = osparc.utils.Utils.deepCloneObject(studyData["accessRights"]);
        // remove collaborator
        delete arCopy[myGid];
        operationPromise = osparc.info.StudyUtils.patchStudyData(studyData, "accessRights", arCopy);
      } else {
        // delete study
        operationPromise = osparc.store.Store.getInstance().deleteStudy(studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromStudyList(studyData.uuid, false))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(() => this.resetSelection());
    },

    __doDeleteStudies: function(studiesData) {
      studiesData.forEach(studyData => this.__doDeleteStudy(studyData));
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
        this.__taskDuplicateReceived(task, studyName);
      }
    },

    __taskDuplicateReceived: function(task, studyName) {
      const duplicateTaskUI = new osparc.task.Duplicate(studyName);
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
          osparc.FlashMessenger.logAs(msg, msgLevel);
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
        this._updateStudyData(duplicatedStudyData);
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
