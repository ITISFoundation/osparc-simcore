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

  members: {
    __servicesAll: null,
    __servicesLatestList: null,

    __reloadService: function(key, version, reload) {
      osparc.store.Store.getInstance().getService(key, version, reload)
        .then(serviceData => {
          this._resetServiceItem(serviceData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    /**
     *  Function that asks the backend for the list of services and sets it
     */
    __reloadServices: function() {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          this.__servicesAll = services;
          const servicesList = [];
          for (const key in services) {
            const latestService = osparc.utils.Services.getLatest(services, key);
            servicesList.push(latestService);
          }
          this.__resetServicesList(servicesList);
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
      preResourcePromises.push(store.getServicesDAGs());
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
      const servicesLayout = this._createResourcesLayout("services");

      this.__addNewServiceButtons();

      osparc.utils.Utils.setIdToWidget(this._resourcesContainer, "servicesList");

      return servicesLayout;
    },

    __createStudyFromService: function(key, version) {
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

      const defaultContext = "workbench";
      let pageContext = defaultContext;

      const data = {
        studyId,
        pageContext
      };
      this.fireDataEvent("startStudy", data);
    },

    _resetServiceItem: function(serviceData) {
      const servicesList = this.__servicesLatestList;
      const index = servicesList.findIndex(service => service["key"] === serviceData["key"] && service["version"] === serviceData["version"]);
      if (index !== -1) {
        servicesList[index] = serviceData;
        this.__resetServicesList(servicesList);
      }
    },

    __resetServicesList: function(servicesList) {
      if (servicesList === undefined) {
        servicesList = this.__servicesLatestList;
      }
      this.__servicesLatestList = servicesList;
      this._resourcesContainer.removeAll();
      servicesList.forEach(service => {
        service["resourceType"] = "service";
        const serviceItem = this.__createServiceItem(service, this._resourcesContainer.getMode());
        serviceItem.addListener("updateQualityService", e => {
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

      const moreInfoButton = this._getMoreInfoMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      const permissionsButton = this.__getPermissionsMenuButton(studyData);
      if (permissionsButton) {
        menu.add(permissionsButton);
      }

      if (osparc.data.model.Node.isComputational(studyData) && "quality" in studyData) {
        const qualityButton = this._getQualityMenuButton(studyData);
        menu.add(qualityButton);
      }

      return menu;
    },

    __getPermissionsMenuButton: function(studyData) {
      const permissionsButton = new qx.ui.menu.Button(this.tr("Sharing"));
      permissionsButton.addListener("execute", () => {
        this.__openPermissions(studyData);
      }, this);

      if (this.__isUserAnyServiceVersionOwner(studyData)) {
        return permissionsButton;
      }

      return null;
    },

    __itemClicked: function(item) {
      const key = item.getUuid();
      this.__createStudyFromService(key, null);
      this.resetSelection();
    },

    _openServiceDetails: function(serviceData) {
      const view = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const serviceVersionsList = new qx.ui.form.SelectBox().set({
        allowGrowX: false,
        font: "text-14"
      });
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const versions = osparc.utils.Services.getVersions(services, serviceData["key"]);
          if (versions) {
            let selectedItem = null;
            versions.reverse().forEach(version => {
              const listItem = new qx.ui.form.ListItem(version).set({
                font: "text-14"
              });
              serviceVersionsList.add(listItem);
              if (serviceData["version"] === version) {
                selectedItem = listItem;
              }
            });
            if (selectedItem) {
              serviceVersionsList.setSelection([selectedItem]);
            }
          }
        });
      view.add(serviceVersionsList);

      const serviceDetails = new osparc.servicecard.Large(serviceData);
      view.add(serviceDetails, {
        flex: 1
      });

      const openButton = new qx.ui.form.Button(this.tr("Open")).set({
        allowGrowX: false,
        alignX: "right"
      });
      osparc.utils.Utils.setIdToWidget(openButton, "startServiceBtn");
      view.add(openButton);

      const title = this.tr("Service information");
      const width = 600;
      const height = 700;
      const win = osparc.ui.window.Window.popUpInWindow(view, title, width, height);

      serviceVersionsList.addListener("changeSelection", () => {
        const selection = serviceVersionsList.getSelection();
        if (selection && selection.length) {
          const serviceVersion = selection[0].getLabel();
          store.getServicesDAGs()
            .then(services => {
              const selectedService = osparc.utils.Services.getFromObject(services, serviceData["key"], serviceVersion);
              serviceDetails.setService(selectedService);
            });
        }
      }, this);

      serviceDetails.addListener("updateService", e => {
        const updatedServiceData = e.getData();
        this._resetServiceItem(updatedServiceData);
      });

      openButton.addListener("execute", () => {
        win.close();
        const currentService = serviceDetails.getService();
        this.__createStudyFromService(currentService["key"], currentService["version"]);
      });
    },

    __openPermissions: function(studyData) {
      const permissionsView = new osparc.component.permissions.Service(studyData);
      const title = this.tr("Available to");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      permissionsView.addListener("updateService", e => {
        const newServiceData = e.getData();
        this._resetServiceItem(newServiceData);
      });
    },

    __openClassifiers: function(studyData) {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (osparc.data.model.Study.isOwner(studyData)) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(studyData);
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedResource = e.getData();
          this._resetServiceItem(updatedResource);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(studyData);
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
      }
    },

    __isUserAnyServiceVersionOwner: function(studyData) {
      if (osparc.utils.Resources.isService(studyData)) {
        const orgIDs = osparc.auth.Data.getInstance().getOrgIds();
        orgIDs.push(osparc.auth.Data.getInstance().getGroupId());

        const ownedServices = osparc.utils.Services.getOwnedServices(this.__servicesAll, studyData["key"]);
        return ownedServices.length;
      }
      return false;
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
      addServiceButton.addListener("execute", () => {
        this.__displayServiceSubmissionForm();
      });
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
    }
  }
});
