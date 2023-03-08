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

/**
 * @asset(form/service.json)
 * @asset(form/service-data.json)
 * @ignore(Headers)
 * @ignore(fetch)
 */

qx.Class.define("osparc.dashboard.ServiceBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function() {
    this._resourceType = "service";
    this.base(arguments);

    this.__sortBy = osparc.component.service.SortServicesButtons.DefaultSorting;
  },

  members: {
    __servicesAll: null,
    __sortBy: null,

    // overridden
    initResources: function() {
      this.__servicesAll = {};
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
          this._hideLoadingPage();
        })
        .catch(err => console.error(err));
    },

    reloadResources: function() {
      this.__reloadServices();
    },

    __reloadServices: function() {
      const store = osparc.store.Store.getInstance();
      store.getAllServices(false, false)
        .then(services => {
          this.__servicesAll = services;
          const favServices = osparc.utils.Utils.localCache.getFavServices();
          const servicesList = [];
          for (const key in services) {
            const latestService = osparc.utils.Services.getLatest(services, key);
            const found = Object.keys(favServices).find(favSrv => favSrv === key);
            latestService.hits = found ? favServices[found]["hits"] : 0;
            // do not list frontend services
            if (!latestService["key"].includes("simcore/services/frontend/")) {
              servicesList.push(latestService);
            }
          }
          this.__setResourcesToList(servicesList);
        })
        .catch(err => {
          console.error(err);
          this.__setResourcesToList([]);
        });
    },

    _updateServiceData: function(serviceData) {
      serviceData["resourceType"] = "service";
      const servicesList = this._resourcesList;
      const index = servicesList.findIndex(service => service["key"] === serviceData["key"] && service["version"] === serviceData["version"]);
      if (index !== -1) {
        servicesList[index] = serviceData;
        this._reloadCards();
      }
    },

    __setResourcesToList: function(servicesList) {
      servicesList.forEach(service => service["resourceType"] = "service");
      osparc.utils.Services.sortObjectsBasedOn(servicesList, this.__sortBy);
      this._resourcesList = servicesList;
      this._reloadCards();
    },

    _reloadCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("servicesList");
      cards.forEach(card => {
        card.addListener("execute", () => this.__itemClicked(card), this);
        this._populateCardMenu(card);
      });
      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __itemClicked: function(card) {
      const key = card.getUuid();
      this._createStudyFromService(key, null);
      this.resetSelection();
    },

    _createStudyFromService: function(key, version) {
      if (!this._checkLoggedIn()) {
        return;
      }

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

    __startStudyById: function(studyId) {
      if (!this._checkLoggedIn()) {
        return;
      }

      this.fireDataEvent("startStudy", studyId);
    },

    // LAYOUT //
    _createLayout: function() {
      this._createResourcesLayout("service");
      const list = this._resourcesContainer.getFlatList();
      if (list) {
        osparc.utils.Utils.setIdToWidget(list, "servicesList");
      }

      this.__addNewServiceButtons();
      this._secondaryBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.__addSortingButtons();
      this._addGroupByButton();
      this._addViewModeButton();

      return this._resourcesContainer;
    },

    __addNewServiceButtons: function() {
      osparc.store.StaticInfo.getInstance().getPlatformName()
        .then(platformName => {
          if (platformName === "dev") {
            const testDataButton = new qx.ui.form.Button(this.tr("Test with data"), "@FontAwesome5Solid/plus-circle/14");
            testDataButton.addListener("execute", () => {
              osparc.utils.Utils.fetchJSON("/resource/form/service-data.json")
                .then(data => {
                  this.__displayServiceSubmissionForm(data);
                });
            });
            this._secondaryBar.add(testDataButton);
          }
        });

      const addServiceButton = new qx.ui.form.Button(this.tr("Submit new service"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.addListener("execute", () => this.__displayServiceSubmissionForm());
      this._secondaryBar.add(addServiceButton);
    },

    __addSortingButtons: function() {
      const containterSortBtns = new osparc.component.service.SortServicesButtons();
      containterSortBtns.addListener("sortBy", e => {
        this.__sortBy = e.getData();
        this.__setResourcesToList(this._resourcesList);
      }, this);
      this._secondaryBar.add(containterSortBtns);
    },
    // LAYOUT //

    // MENU //
    _populateCardMenu: function(card) {
      const menu = card.getMenu();
      const studyData = card.getResourceData();

      const moreInfoButton = this._getMoreOptionsMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }
    },

    __displayServiceSubmissionForm: function(formData) {
      const addServiceWindow = new osparc.ui.window.Window(this.tr("Submit a new service")).set({
        modal: true,
        autoDestroy: true,
        showMinimize: false,
        allowMinimize: false,
        centerOnAppear: true,
        layout: new qx.ui.layout.Grow(),
        width: 600,
        height: 660
      });
      const scroll = new qx.ui.container.Scroll();
      addServiceWindow.add(scroll);
      const form = new osparc.component.form.json.JsonSchemaForm("/resource/form/service.json", formData);
      form.addListener("ready", () => {
        addServiceWindow.open();
      });
      form.addListener("submit", e => {
        const data = e.getData();
        const headers = new Headers();
        headers.append("Accept", "application/json");
        const body = new FormData();
        body.append("metadata", new Blob([JSON.stringify(data.json)], {
          type: "application/json"
        }));
        if (data.files && data.files.length) {
          const size = data.files[0].size;
          const maxSize = 10 * 1024 * 1024; // 10 MB
          if (size > maxSize) {
            osparc.component.message.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          body.append("attachment", data.files[0], data.files[0].name);
        }
        form.setFetching(true);
        fetch("/v0/publications/service-submission", {
          method: "POST",
          headers,
          body
        })
          .then(resp => {
            if (resp.ok) {
              osparc.component.message.FlashMessenger.logAs("Your data was sent to our curation team. We will get back to you shortly.", "INFO");
              addServiceWindow.close();
            } else {
              osparc.component.message.FlashMessenger.logAs(`A problem occured while processing your data: ${resp.statusText}`, "ERROR");
            }
          })
          .finally(() => form.setFetching(false));
      });
      scroll.add(form);
    }
  }
});
