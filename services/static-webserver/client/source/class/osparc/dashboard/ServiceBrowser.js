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
    this.base(arguments);

    this.__sortBy = osparc.component.service.SortServicesButtons.DefaultSorting;
  },

  members: {
    __servicesAll: null,
    __servicesLatestList: null,
    __sortBy: null,

    __reloadService: function(key, version, reload) {
      osparc.store.Store.getInstance().getService(key, version, reload)
        .then(serviceData => {
          this._resetServiceItem(serviceData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __reloadServices: function() {
      const store = osparc.store.Store.getInstance();
      store.getServicesOnly()
        .then(services => {
          const favServices = osparc.utils.Utils.localCache.getFavServices();
          this.__servicesAll = services;
          const servicesList = [];
          for (const key in services) {
            const latestService = osparc.utils.Services.getLatest(services, key);
            const found = Object.keys(favServices).find(favSrv => favSrv === key);
            latestService.hits = found ? favServices[found]["hits"] : 0;
            servicesList.push(latestService);
          }
          this._resetResourcesList(servicesList);
        })
        .catch(err => {
          console.error(err);
        });
    },

    // overridden
    initResources: function() {
      this.__servicesAll = {};
      this.__servicesLatestList = [];
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
      this.__reloadServices();
    },

    _createLayout: function() {
      this._createResourcesLayout("service");

      this.__addNewServiceButtons();
      this.__addSortingButtons();

      osparc.utils.Utils.setIdToWidget(this._resourcesContainer, "servicesList");

      this._resourcesContainer.addListener("changeMode", () => this._resetResourcesList());

      return this._resourcesContainer;
    },

    _createStudyFromService: function(key, version) {
      if (!this._checkLoggedIn()) {
        return;
      }

      this._showLoadingPage(this.tr("Creating Study"));
      osparc.utils.Study.createStudyFromService(key, version)
        .then(studyId => {
          this._hideLoadingPage();
          this.__startStudy(studyId);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __startStudy: function(studyId) {
      if (!this._checkLoggedIn()) {
        return;
      }

      const data = {
        studyId,
        pageContext: "workbench"
      };
      this.fireDataEvent("startStudy", data);
    },

    _resetServiceItem: function(serviceData) {
      serviceData["resourceType"] = "service";
      const servicesList = this.__servicesLatestList;
      const index = servicesList.findIndex(service => service["key"] === serviceData["key"] && service["version"] === serviceData["version"]);
      if (index !== -1) {
        servicesList[index] = serviceData;
        this._resetResourcesList(servicesList);
      }
    },

    // overriden
    _resetResourcesList: function(servicesList) {
      if (servicesList === undefined) {
        servicesList = this.__servicesLatestList;
      }
      this._removeResourceCards();
      this._addResourcesToList(servicesList);
    },

    _addResourcesToList: function(servicesList) {
      const cards = this._resourcesContainer.getChildren();
      osparc.utils.Services.sortObjectsBasedOn(servicesList, this.__sortBy);
      servicesList.forEach(service => {
        if (this.__servicesLatestList.indexOf(service) === -1) {
          this.__servicesLatestList.push(service);
        }
        service["resourceType"] = "service";
        const idx = cards.findIndex(card => card.getUuid() === service["key"]);
        if (idx !== -1) {
          return;
        }
        const serviceItem = this.__createServiceItem(service, this._resourcesContainer.getMode());
        serviceItem.addListener("updateService", e => {
          const updatedServiceData = e.getData();
          updatedServiceData["resourceType"] = "service";
          this._resetServiceItem(updatedServiceData);
        }, this);
        this._resourcesContainer.add(serviceItem);
      });

      osparc.component.filter.UIFilterController.dispatch("searchBarFilter");
    },

    __createServiceItem: function(serviceData) {
      const item = this._createResourceItem(serviceData);
      item.addListener("execute", () => this.__itemClicked(item), this);
      return item;
    },

    _getResourceItemMenu: function(studyData) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const moreInfoButton = this._getMoreOptionsMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      return menu;
    },

    __itemClicked: function(item) {
      const key = item.getUuid();
      this._createStudyFromService(key, null);
      this.resetSelection();
    },

    __addNewServiceButtons: function() {
      osparc.utils.LibVersions.getPlatformName()
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
    },

    __addSortingButtons: function() {
      this._secondaryBar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const containterSortBtns = new osparc.component.service.SortServicesButtons();
      containterSortBtns.addListener("sortBy", e => {
        this.__sortBy = e.getData();
        this._resetResourcesList();
      }, this);
      this._secondaryBar.add(containterSortBtns);
    }
  }
});
