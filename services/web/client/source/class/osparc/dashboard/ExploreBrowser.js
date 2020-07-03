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
 * @ignore(Headers)
 * @ignore(fetch)
 */

qx.Class.define("osparc.dashboard.ExploreBrowser", {
  extend: qx.ui.core.Widget,

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
    }
  },

  members: {
    __loadingIFrame: null,
    __exploreFilters: null,
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
    resetFilter: function() {
      if (this.__exploreFilters) {
        this.__exploreFilters.reset();
      }
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
      this.__showLoadingPage(this.tr("Discovering Templates and Apps"));

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
          this.__hideLoadingPage();
          this.__createResourcesLayout();
          this.__reloadResources();
          this.__attachEventHandlers();
        });
    },

    __reloadResources: function() {
      this.reloadTemplates();
      this.__reloadServices();
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
      const exploreFilters = this.__exploreFilters = new osparc.component.filter.group.StudyFilterGroup("exploreBrowser").set({
        paddingTop: 5
      });
      osparc.utils.Utils.setIdToWidget(exploreFilters.getTextFilter(), "exploreFiltersTextFld");
      this._add(exploreFilters);

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

    __attachEventHandlers: function() {
      const textfield = this.__exploreFilters.getTextFilter().getChildControl("textfield");
      textfield.addListener("appear", () => {
        textfield.focus();
      }, this);
    },

    __createStudyFromService: function(serviceKey, serviceVersion) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      this.__showLoadingPage(this.tr("Creating Study"));
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          if (serviceKey in services) {
            let service = null;
            if (serviceVersion) {
              service= osparc.utils.Services.getFromObject(services, serviceKey, serviceVersion);
            } else {
              service= osparc.utils.Services.getLatest(services, serviceKey);
            }
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
            const params = {
              data: minStudyData
            };
            osparc.data.Resources.fetch("studies", "post", params)
              .then(studyData => {
                this.__startStudy(studyData);
              })
              .catch(er => {
                console.error(er);
              });
          }
        })
        .catch(err => {
          console.error(err);
        });
    },

    __createStudy: function(minStudyData, templateId) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      this.__showLoadingPage(this.tr("Creating ") + (minStudyData.name || this.tr("Study")));

      const params = {
        url: {
          templateId: templateId
        },
        data: minStudyData
      };
      osparc.data.Resources.fetch("studies", "postFromTemplate", params)
        .then(studyData => {
          this.__startStudy(studyData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __startStudy: function(studyData) {
      if (!this.__checkLoggedIn()) {
        return;
      }

      this.__showLoadingPage(this.tr("Starting ") + (studyData.name || this.tr("Study")));
      osparc.store.Store.getInstance().getServicesDAGs()
        .then(() => {
          this.__hideLoadingPage();
          this.__loadStudy(studyData);
        });
    },

    __loadStudy: function(studyData) {
      const study = new osparc.data.model.Study(studyData);
      this.fireDataEvent("startStudy", study);
    },

    __showResourcesLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    __resetTemplatesList: function(tempStudyList) {
      this.__templates = tempStudyList;
      this.__templatesContainer.removeAll();
      this.self().sortTemplateList(tempStudyList);
      tempStudyList.forEach(tempStudy => {
        tempStudy["resourceType"] = "template";
        this.__templatesContainer.add(this.__createStudyItem(tempStudy));
      });
    },

    __resetServicesList: function(servicesList) {
      this.__services = servicesList;
      this.__servicesContainer.removeAll();
      servicesList.forEach(service => {
        service["resourceType"] = "service";
        this.__servicesContainer.add(this.__createStudyItem(service));
      });
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

    __createStudyItem: function(study) {
      let defaultThumbnail = "";
      switch (study["resourceType"]) {
        case "template":
          defaultThumbnail = "@FontAwesome5Solid/copy/50";
          break;
        case "service":
          defaultThumbnail = "@FontAwesome5Solid/paw/50";
          break;
      }
      const tags = study.tags ? osparc.store.Store.getInstance().getTags().filter(tag => study.tags.includes(tag.id)) : [];

      const item = new osparc.dashboard.StudyBrowserButtonItem().set({
        resourceType: study.resourceType,
        uuid: study.uuid,
        studyTitle: study.name,
        studyDescription: study.description,
        creator: study.prjOwner ? study.prjOwner : null,
        accessRights: study.accessRights ? study.accessRights : null,
        lastChangeDate: study.lastChangeDate ? new Date(study.lastChangeDate) : null,
        icon: study.thumbnail || defaultThumbnail,
        tags
      });
      const menu = this.__getStudyItemMenu(item, study);
      item.setMenu(menu);
      item.subscribeToFilterGroup("exploreBrowser");
      item.addListener("execute", () => {
        this.__itemClicked(item);
      }, this);

      return item;
    },

    __getStudyItemMenu: function(item, studyData) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const moreInfoButton = this.__getMoreInfoMenuButton(studyData, true);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      const deleteButton = this.__getDeleteTemplateMenuButton(studyData, true);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }

      return menu;
    },

    __getMoreInfoMenuButton: function(studyData, isTemplate) {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        if (studyData["resourceType"] === "service") {
          const win = new osparc.component.metadata.ServiceStarterWindow(studyData);
          win.addListener("startService", e => {
            const {
              serviceKey,
              serviceVersion
            } = e.getData();
            this.__createStudyFromService(serviceKey, serviceVersion);
            win.close();
          });
          win.open();
          win.center();
        } else {
          const winWidth = 400;
          this.__createStudyDetailsEditor(studyData, winWidth);
        }
      }, this);
      return moreInfoButton;
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
            this.__deleteStudy(studyData, true);
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
        const studyData = this.__templates.find(matchesId);
        this.__createStudyBtnClkd(studyData);
      }
      this.resetSelection();
    },

    __createStudyDetailsEditor: function(studyData, winWidth) {
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(studyData, true, winWidth);
      studyDetails.addListener("updateTemplate", () => this.reloadTemplates(), this);
      studyDetails.addListener("openStudy", () => {
        this.__createStudyBtnClkd(studyData);
      }, this);
      studyDetails.addListener("updateTags", () => {
        this.__resetTemplatesList(osparc.store.Store.getInstance().getTemplates());
      });

      const height = 400;
      const title = this.tr("Study Details Editor");
      const win = osparc.component.metadata.StudyDetailsEditor.popUpInWindow(title, studyDetails, winWidth, height);
      studyDetails.addListener("updateTemplate", () => win.close());
    },

    __createStudyBtnClkd: function(templateData) {
      const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
      minStudyData["name"] = templateData.name;
      minStudyData["description"] = templateData.description;
      this.__createStudy(minStudyData, templateData.uuid);
    },

    __updateDeleteTemplatesButton: function(templateDeleteButton) {
      const templateSelection = this.__templatesContainer.getSelection();
      const canDeleteTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.delete");
      let allMine = Boolean(templateSelection.length) && canDeleteTemplate;
      for (let i=0; i<templateSelection.length && allMine; i++) {
        if (templateSelection[i] instanceof osparc.dashboard.StudyBrowserButtonNew) {
          allMine = false;
        } else {
          const isCurrentUserOwner = this.__isUserOwner(templateSelection[i]);
          allMine &= isCurrentUserOwner;
        }
      }
      if (allMine) {
        const nSelected = templateSelection.length;
        templateDeleteButton.setLabel(nSelected > 1 ? this.tr("Delete selected")+" ("+nSelected+")" : this.tr("Delete"));
        templateDeleteButton.setVisibility("visible");
      } else {
        templateDeleteButton.setVisibility("excluded");
      }
    },

    __deleteStudy: function(studyData, isTemplate = false) {
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
        const permissions = osparc.component.export.Permissions;
        permissions.removeCollaborator(studyData, myGid);
        params["data"] = studyData;
        operationPromise = osparc.data.Resources.fetch(isTemplate ? "templates" : "studies", "put", params);
      } else {
        // delete study
        operationPromise = osparc.data.Resources.fetch(isTemplate ? "templates" : "studies", "delete", params, studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromStudyList(studyData.uuid, isTemplate))
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        });
    },

    __createConfirmWindow: function(isMulti) {
      const msg = isMulti ? this.tr("Are you sure you want to delete the studies?") : this.tr("Are you sure you want to delete the study?");
      return new osparc.ui.window.Confirmation(msg);
    },

    __showLoadingPage: function(label) {
      this.__hideLoadingPage();

      this.__showResourcesLayout(false);

      if (this.__loadingIFrame === null) {
        this.__loadingIFrame = new osparc.ui.message.Loading(label);
      } else {
        this.__loadingIFrame.setHeader(label);
      }
      this._add(this.__loadingIFrame, {
        flex: 1
      });
    },

    __hideLoadingPage: function() {
      if (this.__loadingIFrame) {
        const idx = this._indexOf(this.__loadingIFrame);
        if (idx !== -1) {
          this._remove(this.__loadingIFrame);
        }
      }

      this.__showResourcesLayout(true);
    },

    __isUserOwner: function(studyData) {
      const myEmail = osparc.auth.Data.getInstance().getEmail();
      if ("prjOwner" in studyData) {
        return studyData.prjOwner === myEmail;
      } else if ("getCreator" in studyData) {
        return studyData.getCreator() === myEmail;
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
      const addServiceWindow = new qx.ui.window.Window(this.tr("Submit a new service")).set({
        appearance: "service-window",
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
              osparc.component.message.FlashMessenger.logAs("A problem occured while processing your data", "ERROR");
            }
          })
          .finally(() => form.setFetching(false));
      });
      scroll.add(form);
    }
  }
});
