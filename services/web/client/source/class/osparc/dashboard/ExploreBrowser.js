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
  extend: osparc.dashboard.ResourceBrowserBase,

  members: {
    __servicesContainer: null,
    __templates: null,
    __servicesAll: null,
    __servicesLatestList: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "scroll-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          control.getChildControl("pane").addListener("scrollY", () => {
            this._moreStudiesRequired();
          }, this);
          break;
        case "resources-container": {
          const scroll = this.getChildControl("scroll-container");
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(16));
          scroll.add(control);
          break;
        }
        case "templates-layout": {
          control = this.__createTemplatesLayout();
          const resourcesContainer = this.getChildControl("resources-container");
          resourcesContainer.add(control);
          break;
        }
        case "services-layout": {
          control = this.__createServicesLayout();
          const resourcesContainer = this.getChildControl("resources-container");
          resourcesContainer.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this._studiesContainer) {
        this._studiesContainer.resetSelection();
      }
      if (this.__servicesContainer) {
        this.__servicesContainer.resetSelection();
      }
    },

    _reloadTemplate: function(templateId) {
      const params = {
        url: {
          "studyId": templateId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this._resetTemplateItem(studyData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __reloadService: function(key, version, reload) {
      osparc.store.Store.getInstance().getService(key, version, reload)
        .then(serviceData => {
          this._resetServiceItem(serviceData);
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
    reloadStudies: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        this._requestStudies(true);
      } else {
        this._resetTemplatesList([]);
      }
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
    _initResources: function() {
      this._showLoadingPage(this.tr("Starting..."));

      this.__templates = [];
      this.__servicesAll = {};
      this.__servicesLatestList = [];
      const resourcePromises = [];
      const store = osparc.store.Store.getInstance();
      resourcePromises.push(store.getServicesDAGs(true));
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        resourcePromises.push(osparc.data.Resources.get("tags"));
      }

      Promise.all(resourcePromises)
        .then(() => {
          this.getChildControl("templates-layout");
          this.getChildControl("services-layout");
          this.__reloadResources();
          this._hideLoadingPage();
        });
    },

    __reloadResources: function() {
      this.reloadStudies();
      this.__reloadServices();
    },

    // overridden
    _showMainLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    __createCollapsibleView: function(title) {
      const userStudyLayout = new osparc.component.widget.CollapsibleView(title);
      userStudyLayout.getChildControl("title").set({
        font: "title-16"
      });
      userStudyLayout._getLayout().setSpacing(8); // eslint-disable-line no-underscore-dangle
      return userStudyLayout;
    },

    __createTemplatesLayout: function() {
      const tempStudyLayout = this.__createCollapsibleView(this.tr("Templates"));

      const titleBarBtnsContainerRight = tempStudyLayout.getTitleBarBtnsContainerRight();
      const viewGridBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/apps/18");
      titleBarBtnsContainerRight.add(viewGridBtn);
      const viewListBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/reorder/18");
      titleBarBtnsContainerRight.add(viewListBtn);
      const group = new qx.ui.form.RadioGroup();
      group.add(viewGridBtn);
      group.add(viewListBtn);

      const templateStudyContainer = this._studiesContainer = this.__createResourceListLayout();
      osparc.utils.Utils.setIdToWidget(templateStudyContainer, "templateStudiesList");
      tempStudyLayout.setContent(templateStudyContainer);

      const loadingTemplatesBtn = this.__createLoadMoreTemplatesButton();
      templateStudyContainer.add(loadingTemplatesBtn);

      viewGridBtn.addListener("execute", () => this.__setTemplatesContainerMode("grid"));
      viewListBtn.addListener("execute", () => this.__setTemplatesContainerMode("list"));

      templateStudyContainer.addListener("changeVisibility", () => this._moreStudiesRequired());
      templateStudyContainer.addListener("changeMode", () => this._resetTemplatesList());

      return tempStudyLayout;
    },

    __createLoadMoreTemplatesButton: function(mode = "grid") {
      const loadingTemplatesBtn = this._loadingStudiesBtn = (mode === "grid") ? new osparc.dashboard.GridButtonLoadMore() : new osparc.dashboard.ListButtonLoadMore();
      osparc.utils.Utils.setIdToWidget(loadingTemplatesBtn, "templatesLoading");
      return loadingTemplatesBtn;
    },

    __createServicesLayout: function() {
      const servicesLayout = this.__createCollapsibleView(this.tr("Services"));

      const titleBarBtnsContainerLeft = servicesLayout.getTitleBarBtnsContainerLeft();
      this.__addNewServiceButtons(titleBarBtnsContainerLeft);

      const titleBarBtnsContainerRight = servicesLayout.getTitleBarBtnsContainerRight();
      const viewGridBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/apps/18");
      titleBarBtnsContainerRight.add(viewGridBtn);
      const viewListBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/reorder/18");
      titleBarBtnsContainerRight.add(viewListBtn);
      const group = new qx.ui.form.RadioGroup();
      group.add(viewGridBtn);
      group.add(viewListBtn);

      const servicesContainer = this.__servicesContainer = this.__createResourceListLayout();
      osparc.utils.Utils.setIdToWidget(servicesContainer, "servicesList");
      servicesLayout.setContent(servicesContainer);

      viewGridBtn.addListener("execute", () => this.__setServicesContainerMode("grid"));
      viewListBtn.addListener("execute", () => this.__setServicesContainerMode("list"));

      servicesContainer.addListener("changeMode", () => this.__resetServicesList());

      return servicesLayout;
    },

    __createStudyFromService: function(key, version) {
      if (!this.__checkLoggedIn()) {
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

    _createStudyFromTemplate: function(templateData) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      this._showLoadingPage(this.tr("Creating ") + (templateData.name || this.tr("Study")));
      osparc.utils.Study.createStudyFromTemplate(templateData)
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
      if (!this.__checkLoggedIn()) {
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
      this._resetTemplatesList(templatesList);
    },

    _resetTemplatesList: function(tempStudyList) {
      if (tempStudyList === undefined) {
        tempStudyList = this.__templates;
      }
      this.__templates = tempStudyList;

      // check Load More card
      let loadMoreFetching = null;
      let loadMoreVisibility = null;
      const loadMoreCard = this._studiesContainer.getChildren().find(el => el === this._loadingStudiesBtn);
      if (loadMoreCard) {
        loadMoreFetching = loadMoreCard.getFetching();
        loadMoreVisibility = loadMoreCard.getVisibility();
      }

      this._studiesContainer.removeAll();

      osparc.dashboard.ResourceBrowserBase.sortStudyList(tempStudyList);
      tempStudyList.forEach(tempStudy => {
        tempStudy["resourceType"] = "template";
        const templateItem = this.__createStudyItem(tempStudy, this._studiesContainer.getMode());
        templateItem.addListener("updateQualityTemplate", e => {
          const updatedTemplateData = e.getData();
          updatedTemplateData["resourceType"] = "template";
          this._resetTemplateItem(updatedTemplateData);
        }, this);
        this._studiesContainer.add(templateItem);
      });

      if (loadMoreCard) {
        const newLoadMoreBtn = this.__createLoadMoreTemplatesButton(this._studiesContainer.getMode());
        newLoadMoreBtn.set({
          fetching: loadMoreFetching,
          visibility: loadMoreVisibility
        });
        this._studiesContainer.add(newLoadMoreBtn);
      }

      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    _addStudiesToList: function(newTemplatesList) {
      osparc.dashboard.ResourceBrowserBase.sortStudyList(newTemplatesList);
      const templatesList = this._studiesContainer.getChildren();
      newTemplatesList.forEach(template => {
        if (this.__templates.indexOf(template) === -1) {
          this.__templates.push(template);
        }

        template["resourceType"] = "template";
        const idx = templatesList.findIndex(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === template["uuid"]);
        if (idx !== -1) {
          return;
        }
        const templateItem = this.__createStudyItem(template, this._studiesContainer.getMode());
        this._studiesContainer.add(templateItem);
      });
      osparc.dashboard.ResourceBrowserBase.sortStudyList(templatesList.filter(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)));
      const idx = templatesList.findIndex(card => card instanceof osparc.dashboard.GridButtonLoadMore);
      if (idx !== -1) {
        templatesList.push(templatesList.splice(idx, 1)[0]);
      }
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
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
      this.__servicesContainer.removeAll();
      servicesList.forEach(service => {
        service["resourceType"] = "service";
        const serviceItem = this.__createStudyItem(service, this.__servicesContainer.getMode());
        serviceItem.addListener("updateQualityService", e => {
          const updatedServiceData = e.getData();
          updatedServiceData["resourceType"] = "service";
          this._resetServiceItem(updatedServiceData);
        }, this);
        this.__servicesContainer.add(serviceItem);
      });
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    __removeFromStudyList: function(studyId) {
      const studyContainer = this._studiesContainer;
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
      const spacing = osparc.dashboard.GridButtonBase.SPACING;
      return new osparc.component.form.ToggleButtonContainer(new qx.ui.layout.Flow(spacing, spacing));
    },

    __setTemplatesContainerMode: function(mode = "grid") {
      const spacing = mode === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
      this._studiesContainer.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
      this._studiesContainer.setMode(mode);
    },

    __setServicesContainerMode: function(mode = "grid") {
      const spacing = mode === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
      this.__servicesContainer.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
      this.__servicesContainer.setMode(mode);
    },

    __createStudyItem: function(studyData, containerMode = "grid") {
      const tags = studyData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => studyData.tags.includes(tag.id)) : [];

      const item = containerMode === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      item.set({
        resourceData: studyData,
        tags
      });

      const menu = this.__getStudyItemMenu(studyData);
      item.setMenu(menu);
      item.subscribeToFilterGroup("sideSearchFilter");
      item.addListener("execute", () => {
        this.__itemClicked(item);
      }, this);

      return item;
    },

    __getStudyItemMenu: function(studyData) {
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

      if (osparc.utils.Resources.isService(studyData) && osparc.data.model.Node.isComputational(studyData) && "quality" in studyData) {
        const qualityButton = this._getQualityMenuButton(studyData);
        menu.add(qualityButton);
      }

      const classifiersButton = this.__getClassifiersMenuButton(studyData);
      if (classifiersButton) {
        menu.add(classifiersButton);
      }

      const studyServicesButton = this.__getStudyServicesMenuButton(studyData);
      if (studyServicesButton) {
        menu.add(studyServicesButton);
      }

      if (osparc.utils.Resources.isTemplate(studyData) && osparc.data.model.Study.isOwner(studyData)) {
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

    __getPermissionsMenuButton: function(studyData) {
      const permissionsButton = new qx.ui.menu.Button(this.tr("Sharing"));
      permissionsButton.addListener("execute", () => {
        this.__openPermissions(studyData);
      }, this);

      if (osparc.utils.Resources.isTemplate(studyData) && this.__isUserTemplateOwner(studyData)) {
        return permissionsButton;
      }

      if (osparc.utils.Resources.isService(studyData) && this.__isUserAnyServiceVersionOwner(studyData)) {
        return permissionsButton;
      }

      return null;
    },

    __getClassifiersMenuButton: function(studyData) {
      if (!osparc.data.Permissions.getInstance().canDo("study.classifier")) {
        return null;
      }

      const classifiersButton = new qx.ui.menu.Button(this.tr("Classifiers"));
      classifiersButton.addListener("execute", () => {
        this.__openClassifiers(studyData);
      }, this);
      return classifiersButton;
    },

    __getStudyServicesMenuButton: function(studyData) {
      if (osparc.utils.Resources.isService(studyData)) {
        return null;
      }

      const studyServicesButton = new qx.ui.menu.Button(this.tr("Services"));
      studyServicesButton.addListener("execute", () => {
        const servicesInStudy = new osparc.component.metadata.ServicesInStudy(studyData);
        const title = this.tr("Services in Study");
        osparc.ui.window.Window.popUpInWindow(servicesInStudy, title, 650, 300);
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
      const isCurrentUserOwner = this.__isUserTemplateOwner(studyData);
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
        const key = item.getUuid();
        this.__createStudyFromService(key, null);
      } else {
        const matchesId = study => study.uuid === item.getUuid();
        const templateData = this.__templates.find(matchesId);
        this._createStudyFromTemplate(templateData);
      }
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
      if (osparc.utils.Resources.isTemplate(studyData)) {
        this.__openTemplatePermissions(studyData);
      } else if (osparc.utils.Resources.isService(studyData)) {
        this.__openServicePermissions(studyData);
      }
    },

    __openServicePermissions: function(serviceData) {
      const permissionsView = new osparc.component.permissions.Service(serviceData);
      const title = this.tr("Available to");
      osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
      permissionsView.addListener("updateService", e => {
        const newServiceData = e.getData();
        this._resetServiceItem(newServiceData);
      });
    },

    __openTemplatePermissions: function(studyData) {
      const permissionsView = osparc.studycard.Utils.openAccessRights(studyData);
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this._resetTemplateItem(updatedData);
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
          if (osparc.utils.Resources.isTemplate(studyData)) {
            this._resetTemplateItem(updatedResource);
          } else if (osparc.utils.Resources.isService(studyData)) {
            this._resetServiceItem(updatedResource);
          }
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(studyData);
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
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

    __isUserTemplateOwner: function(studyData) {
      if (osparc.utils.Resources.isTemplate(studyData)) {
        return osparc.data.model.Study.isOwner(studyData);
      }
      return false;
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

    __addNewServiceButtons: function(layout) {
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
