/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

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

qx.Class.define("osparc.dashboard.ExploreBrowser", {
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__initResources();
  },

  events: {
    "startStudy": "qx.event.type.Data"
  },

  statics: {
    sortTemplateList: function(studyList) {
      let sortByProperty = function(prop) {
        return function(a, b) {
          if (prop === "lastChangeDate") {
            return new Date(b[prop]) - new Date(a[prop]);
          }
          if (typeof a[prop] == "number") {
            return a[prop] - b[prop];
          }
          if (a[prop] < b[prop]) {
            return -1;
          } else if (a[prop] > b[prop]) {
            return 1;
          }
          return 0;
        };
      };
      studyList.sort(sortByProperty("lastChangeDate"));
    },

    isTemplate: function(studyData) {
      return (studyData["resourceType"] === "template");
    },

    isService: function(studyData) {
      return (studyData["resourceType"] === "service");
    }
  },

  members: {
    __templatesContainer: null,
    __servicesContainer: null,
    __templates: null,
    __services: null,

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this.__templatesContainer) {
        this.__templatesContainer.resetSelection();
      }
      if (this.__servicesContainer) {
        this.__servicesContainer.resetSelection();
      }
    },

    __reloadTemplate: function(studyId) {
      const params = {
        url: {
          "projectId": studyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this.__resetTemplateItem(studyData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __reloadService: function(serviceKey, serviceVersion, reload) {
      osparc.store.Store.getInstance().getService(serviceKey, serviceVersion, reload)
        .then(serviceData => {
          this.__resetServiceItem(serviceData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __checkLoggedIn: function() {
      let isLogged = osparc.auth.Manager.getInstance().isLoggedIn();
      if (!isLogged) {
        const msg = this.tr("You need to be logged in to create a study");
        osparc.component.message.FlashMessenger.getInstance().logAs(msg);
      }
      return isLogged;
    },

    /**
     *  Function that asks the backend for the list of template studies and sets it
     */
    reloadTemplates: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        osparc.data.Resources.get("templates")
          .then(templates => {
            this.__resetTemplatesList(templates);
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        this.__resetTemplatesList([]);
      }
    },

    /**
     *  Function that asks the backend for the list of services and sets it
     */
    __reloadServices: function() {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const servicesList = [];
          for (const serviceKey in services) {
            const latestService = osparc.utils.Services.getLatest(services, serviceKey);
            servicesList.push(latestService);
          }
          this.__resetServicesList(servicesList);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __initResources: function() {
      this._showLoadingPage(this.tr("Discovering Templates and Apps"));

      this.__templates = [];
      this.__services = [];
      const servicesTags = this.__getTags();
      const store = osparc.store.Store.getInstance();
      const servicesPromise = store.getServicesDAGs(true);

      Promise.all([
        servicesTags,
        servicesPromise
      ])
        .then(() => {
          this._hideLoadingPage();
          this.__createResourcesLayout();
          this.__reloadResources();
        });
    },

    __reloadResources: function() {
      this.reloadTemplates();
      this.__reloadServices();
    },

    // overridden
    _showMainLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    __getTags: function() {
      return new Promise((resolve, reject) => {
        if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
          osparc.data.Resources.get("tags")
            .catch(console.error)
            .finally(() => resolve());
        } else {
          resolve();
        }
      });
    },

    __createResourcesLayout: function() {
      const exploreBrowserLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(16));

      const tempStudyLayout = this.__createTemplatesLayout();
      exploreBrowserLayout.add(tempStudyLayout);

      const servicesLayout = this.__createServicesLayout();
      exploreBrowserLayout.add(servicesLayout);

      const scrollStudies = new qx.ui.container.Scroll();
      scrollStudies.add(exploreBrowserLayout);
      this._add(scrollStudies, {
        flex: 1
      });
    },

    __createButtonsLayout: function(title, content) {
      const userStudyLayout = new osparc.component.widget.CollapsibleView(title);
      userStudyLayout.getChildControl("title").set({
        font: "title-16"
      });
      userStudyLayout._getLayout().setSpacing(8); // eslint-disable-line no-underscore-dangle
      userStudyLayout.setContent(content);
      return userStudyLayout;
    },

    __createTemplatesLayout: function() {
      const templateStudyContainer = this.__templatesContainer = this.__createResourceListLayout();
      osparc.utils.Utils.setIdToWidget(templateStudyContainer, "templateStudiesList");
      const tempStudyLayout = this.__createButtonsLayout(this.tr("Templates"), templateStudyContainer);
      return tempStudyLayout;
    },

    __createServicesLayout: function() {
      const servicesContainer = this.__servicesContainer = this.__createResourceListLayout();
      osparc.utils.Utils.setIdToWidget(servicesContainer, "servicesList");
      const servicesLayout = this.__createButtonsLayout(this.tr("Services"), servicesContainer);

      const servicesTitleContainer = servicesLayout.getTitleBar();
      this.__addNewServiceButtons(servicesTitleContainer);

      return servicesLayout;
    },

    __createStudyFromService: function(serviceKey, serviceVersion) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      this._showLoadingPage(this.tr("Creating Study"));
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          if (serviceKey in services) {
            const service = serviceVersion ? osparc.utils.Services.getFromObject(services, serviceKey, serviceVersion) : osparc.utils.Services.getLatest(services, serviceKey);
            const newUuid = osparc.utils.Utils.uuidv4();
            const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
            minStudyData["name"] = service["name"];
            minStudyData["workbench"] = {};
            minStudyData["workbench"][newUuid] = {
              "key": service["key"],
              "version": service["version"],
              "label": service["name"],
              "inputs": {},
              "inputNodes": [],
              "thumbnail": "",
              "position": {
                "x": 50,
                "y": 50
              }
            };
            store.getInaccessibleServices(minStudyData)
              .then(inaccessibleServices => {
                if (inaccessibleServices.length) {
                  this._hideLoadingPage();
                  const msg = osparc.utils.Study.getInaccessibleServicesMsg(inaccessibleServices);
                  throw new Error(msg);
                }
                const params = {
                  data: minStudyData
                };
                osparc.data.Resources.fetch("studies", "post", params)
                  .then(studyData => {
                    this._hideLoadingPage();
                    this.__startStudy(studyData["uuid"]);
                  })
                  .catch(er => {
                    console.error(er);
                  });
              });
          }
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __createStudyFromTemplate: function(templateData) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      this._showLoadingPage(this.tr("Creating ") + (templateData.name || this.tr("Study")));

      const store = osparc.store.Store.getInstance();
      store.getInaccessibleServices(templateData)
        .then(inaccessibleServices => {
          if (inaccessibleServices.length) {
            const msg = osparc.utils.Study.getInaccessibleServicesMsg(inaccessibleServices);
            throw new Error(msg);
          }
          const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
          minStudyData["name"] = templateData.name;
          minStudyData["description"] = templateData.description;
          const params = {
            url: {
              templateId: templateData.uuid
            },
            data: minStudyData
          };
          osparc.data.Resources.fetch("studies", "postFromTemplate", params)
            .then(studyData => {
              this._hideLoadingPage();
              this.__startStudy(studyData["uuid"]);
            })
            .catch(err => {
              console.error(err);
            });
        })
        .catch(err => {
          osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          this._hideLoadingPage();
          return;
        });
    },

    __startStudy: function(studyId) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      const data = {
        studyId: studyId
      };
      this.fireDataEvent("startStudy", data);
    },

    __resetTemplateItem: function(templateData) {
      const templatesList = this.__templates;
      const index = templatesList.findIndex(template => template["uuid"] === templateData["uuid"]);
      if (index === -1) {
        templatesList.push(templateData);
      } else {
        templatesList[index] = templateData;
      }
      this.__resetTemplatesList(templatesList);
    },

    __resetTemplatesList: function(tempStudyList) {
      this.__templates = tempStudyList;
      this.__templatesContainer.removeAll();
      this.self().sortTemplateList(tempStudyList);
      tempStudyList.forEach(tempStudy => {
        tempStudy["resourceType"] = "template";
        this.__templatesContainer.add(this.__createStudyItem(tempStudy));
      });
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    __resetServiceItem: function(serviceData) {
      const servicesList = this.__services;
      const index = servicesList.findIndex(service => service["key"] === serviceData["key"]);
      if (index === -1) {
        servicesList.push(serviceData);
      } else {
        servicesList[index] = serviceData;
      }
      this.__resetServicesList(servicesList);
    },

    __resetServicesList: function(servicesList) {
      this.__services = servicesList;
      this.__servicesContainer.removeAll();
      servicesList.forEach(service => {
        service["resourceType"] = "service";
        this.__servicesContainer.add(this.__createStudyItem(service));
      });
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    __removeFromStudyList: function(studyId) {
      const studyContainer = this.__templatesContainer;
      const items = studyContainer.getChildren();
      for (let i=0; i<items.length; i++) {
        const item = items[i];
        if (item.getUuid && studyId === item.getUuid()) {
          studyContainer.remove(item);
          return;
        }
      }
    },

    __createResourceListLayout: function() {
      const spacing = osparc.dashboard.StudyBrowserButtonBase.SPACING;
      return new osparc.component.form.ToggleButtonContainer(new qx.ui.layout.Flow(spacing, spacing));
    },

    __createStudyItem: function(studyData) {
      const tags = studyData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => studyData.tags.includes(tag.id)) : [];

      const item = new osparc.dashboard.StudyBrowserButtonItem().set({
        resourceData: studyData,
        tags
      });

      const menu = this.__getStudyItemMenu(item, studyData);
      item.setMenu(menu);
      item.subscribeToFilterGroup("sideSearchFilter");
      item.addListener("execute", () => {
        this.__itemClicked(item);
      }, this);

      return item;
    },

    __getStudyItemMenu: function(item, studyData) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const moreInfoButton = this.__getMoreInfoMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      const classifiersButton = this.__getClassifiersMenuButton(studyData);
      if (classifiersButton) {
        menu.add(classifiersButton);
      }

      const permissionsButton = this.__getPermissionsMenuButton(studyData);
      if (permissionsButton) {
        menu.add(permissionsButton);
      }

      const studyServicesButton = this.__getStudyServicesMenuButton(studyData);
      if (studyServicesButton) {
        menu.add(studyServicesButton);
      }

      if (this.self().isTemplate(studyData) && osparc.data.model.Study.isOwner(studyData)) {
        const publishOnPortalButton = this.__getPublishOnPortalMenuButton(studyData);
        menu.add(publishOnPortalButton);
      }

      const deleteButton = this.__getDeleteTemplateMenuButton(studyData);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }

      return menu;
    },

    __getMoreInfoMenuButton: function(studyData) {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        if (this.self().isTemplate(studyData)) {
          const winWidth = 400;
          this.__createStudyDetailsEditor(studyData, winWidth);
        } else if (this.self().isService(studyData)) {
          this.__createServiceDetailsEditor(studyData);
        }
      }, this);
      return moreInfoButton;
    },

    __getClassifiersMenuButton: function(studyData) {
      const isCurrentUserOwner = this.__isUserOwner(studyData);
      if (!isCurrentUserOwner) {
        return null;
      }

      if (!osparc.data.Permissions.getInstance().canDo("study.classifier")) {
        return null;
      }

      const classifiersButton = new qx.ui.menu.Button(this.tr("Classifiers"));
      classifiersButton.addListener("execute", () => {
        this.__openClassifiers(studyData);
      }, this);
      return classifiersButton;
    },

    __openClassifiers: function(studyData) {
      const classifiersEditor = new osparc.dashboard.ClassifiersEditor(studyData, this.self().isTemplate(studyData));
      const title = this.tr("Classifiers");
      osparc.ui.window.Window.popUpInWindow(classifiersEditor, title, 400, 400);
      classifiersEditor.addListener("updateClassifiers", e => {
        if (this.self().isTemplate(studyData)) {
          const studyId = e.getData();
          this.__reloadTemplate(studyId);
        } else if (this.self().isService(studyData)) {
          const serviceKey = e.getData();
          this.__reloadService(serviceKey, studyData.version);
        }
      }, this);
    },

    __getPermissionsMenuButton: function(studyData) {
      const isCurrentUserOwner = this.__isUserOwner(studyData);
      if (!isCurrentUserOwner) {
        return null;
      }

      const permissionsButton = new qx.ui.menu.Button(this.tr("Permissions"));
      permissionsButton.addListener("execute", () => {
        if (this.self().isTemplate(studyData)) {
          this.__openTemplatePermissions(studyData);
        } else if (this.self().isService(studyData)) {
          this.__openServicePermissions(studyData);
        }
      }, this);
      return permissionsButton;
    },

    __getStudyServicesMenuButton: function(studyData) {
      if (this.self().isService(studyData)) {
        return null;
      }

      const studyServicesButton = new qx.ui.menu.Button(this.tr("Services"));
      studyServicesButton.addListener("execute", () => {
        const servicesInStudy = new osparc.component.metadata.ServicesInStudy(studyData);
        const title = this.tr("Services in Study");
        osparc.ui.window.Window.popUpInWindow(servicesInStudy, title, 400, 100);
      }, this);
      return studyServicesButton;
    },

    __getPublishOnPortalMenuButton: function() {
      const publishOnPortalButton = new qx.ui.menu.Button(this.tr("Publish on Portal"));
      publishOnPortalButton.addListener("execute", () => {
        const msg = this.tr("Not yet implemented");
        osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO");
      }, this);
      return publishOnPortalButton;
    },

    __getDeleteTemplateMenuButton: function(studyData) {
      const isCurrentUserOwner = this.__isUserOwner(studyData);
      if (!isCurrentUserOwner) {
        return null;
      }

      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => {
        const win = this.__createConfirmWindow(false);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteTemplate(studyData);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __itemClicked: function(item) {
      if (item.isResourceType("service")) {
        const serviceKey = item.getUuid();
        this.__createStudyFromService(serviceKey, null);
      } else {
        const matchesId = study => study.uuid === item.getUuid();
        const templateData = this.__templates.find(matchesId);
        this.__createStudyFromTemplate(templateData);
      }
      this.resetSelection();
    },

    __createStudyDetailsEditor: function(templateData, winWidth) {
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(templateData, true, winWidth);
      studyDetails.addListener("updateTemplate", () => this.reloadTemplates(), this);
      studyDetails.addListener("openStudy", () => {
        this.__createStudyFromTemplate(templateData);
      }, this);
      studyDetails.addListener("updateTags", () => {
        this.__resetTemplatesList(osparc.store.Store.getInstance().getTemplates());
      });

      const height = 400;
      const title = this.tr("Study Details Editor");
      const win = osparc.ui.window.Window.popUpInWindow(studyDetails, title, winWidth, height);
      studyDetails.addListener("updateTemplate", () => win.close());
    },

    __createServiceDetailsEditor: function(serviceData) {
      const serviceDetailsEditor = new osparc.component.metadata.ServiceDetailsEditor(serviceData);
      const title = this.tr("Service information") + " · " + serviceData.name;
      const win = osparc.ui.window.Window.popUpInWindow(serviceDetailsEditor, title, 700, 800);
      serviceDetailsEditor.addListener("startService", e => {
        const {
          serviceKey,
          serviceVersion
        } = e.getData();
        this.__createStudyFromService(serviceKey, serviceVersion);
        win.close();
      });
      serviceDetailsEditor.addListener("updateService", e => {
        const newServiceData = e.getData();
        this.__resetServiceItem(newServiceData);
        win.close();
      });
    },

    __openServicePermissions: function(serviceData) {
      const permissionsView = new osparc.component.export.ServicePermissions(serviceData);
      const title = this.tr("Available to");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      permissionsView.addListener("updateService", e => {
        const newServiceData = e.getData();
        this.__resetServiceItem(newServiceData);
      });
    },

    __openTemplatePermissions: function(studyData) {
      const permissionsView = new osparc.component.export.StudyPermissions(studyData);
      const title = this.tr("Available to");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      permissionsView.addListener("updateStudy", e => {
        const studyId = e.getData();
        console.log(studyId);
        this.reloadTemplates();
      });
    },

    __deleteTemplate: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      const params = {
        url: {
          projectId: studyData.uuid
        }
      };
      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        // remove collaborator
        osparc.component.export.StudyPermissions.removeCollaborator(studyData, myGid);
        params["data"] = studyData;
        operationPromise = osparc.data.Resources.fetch("templates", "put", params);
      } else {
        // delete study
        operationPromise = osparc.data.Resources.fetch("templates", "delete", params, studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromStudyList(studyData.uuid))
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        });
    },

    __createConfirmWindow: function(isMulti) {
      const msg = isMulti ? this.tr("Are you sure you want to delete the studies?") : this.tr("Are you sure you want to delete the study?");
      return new osparc.ui.window.Confirmation(msg);
    },

    __isUserOwner: function(studyData) {
      if (this.self().isTemplate(studyData)) {
        return osparc.data.model.Study.isOwner(studyData);
      } else if (this.self().isService(studyData)) {
        const myEmail = osparc.auth.Data.getInstance().getEmail();
        return studyData.owner === myEmail;
      }
      return false;
    },

    __addNewServiceButtons: function(layout) {
      layout.add(new qx.ui.core.Spacer(20, null));


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
            layout.add(testDataButton);
          }
        });

      const addServiceButton = new qx.ui.form.Button(this.tr("Submit new service"), "@FontAwesome5Solid/plus-circle/14");
      addServiceButton.addListener("execute", () => {
        this.__displayServiceSubmissionForm();
      });
      layout.add(addServiceButton);
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
          const maxSize = 10; // 10 MB
          if (size > maxSize * 1024 * 1024) {
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
