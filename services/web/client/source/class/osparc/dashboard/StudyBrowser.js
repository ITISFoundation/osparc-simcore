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
 * Widget that shows two lists of studies and study editor form:
 * - List1: User's studies (StudyBrowserButtonItem)
 * - List2: Template studies to start from (StudyBrowserButtonItem)
 * - Form: Extra editable information of the selected study
 *
 * It is the entry point to start editing or creatina new study.
 *
 * Also takes care of retrieveing the list of services and pushing the changes in the metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let prjBrowser = this.__serviceBrowser = new osparc.dashboard.StudyBrowser();
 *   this.getRoot().add(prjBrowser);
 * </pre>
 */

qx.Class.define("osparc.dashboard.StudyBrowser", {
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
    sortStudyList: function(studyList) {
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

    resources: {
      "templates": {
        "label": "New studies"
      },
      "services": {
        "label": "Apps"
      }
    }
  },

  members: {
    __loadingIFrame: null,
    __studyFilters: null,
    __userStudyContainer: null,
    __templateStudyContainer: null,
    __servicesContainer: null,
    __userStudies: null,
    __templateStudies: null,
    __services: null,
    __newStudyBtn: null,

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this.__studyFilters) {
        this.__studyFilters.reset();
      }
      this.__itemSelected(null);
    },

    __reloadUserStudy: function(studyId) {
      const params = {
        url: {
          projectId: studyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this.__resetStudyItem(studyData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    /**
     * Function that asks the backend for the list of studies belonging to the user
     * and sets it
     */
    reloadUserStudies: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.user.read")) {
        osparc.data.Resources.get("studies")
          .then(studies => {
            this.__resetStudyList(studies);
            this.__itemSelected(null);
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        this.__resetStudyList([]);
      }
    },

    /**
     *  Function that asks the backend for the list of template studies and sets it
     */
    reloadTemplateStudies: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.templates.read")) {
        osparc.data.Resources.get("templates")
          .then(templates => {
            this.__resetTemplateList(templates);
            this.__itemSelected(null);
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        this.__resetTemplateList([]);
      }
    },

    /**
     *  Function that asks the backend for the list of services and sets it
     */
    reloadServices: function() {
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          const servicesList = [];
          for (const serviceKey in services) {
            const latestService = osparc.utils.Services.getLatest(services, serviceKey);
            servicesList.push(latestService);
          }
          this.__resetServicesList(servicesList);
          this.__itemSelected(null);
        })
        .catch(err => {
          console.error(err);
        });
    },

    __initResources: function() {
      this.__showLoadingPage(this.tr("Loading Studies"));

      const servicesTags = this.__getTags();
      const store = osparc.store.Store.getInstance();
      const servicesPromise = store.getServicesDAGs(true);

      Promise.all([
        servicesTags,
        servicesPromise
      ])
        .then(() => {
          this.__hideLoadingPage();
          this.__createStudiesLayout();
          this.__reloadResources();
          this.__attachEventHandlers();
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            this.__getStudyAndStart(loadStudyId);
          }
        });
    },

    __reloadResources: function() {
      this.__getActiveStudy();
      this.reloadUserStudies();
      this.reloadTemplateStudies();
      this.reloadServices();
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

    __createStudiesLayout: function() {
      const studyFilters = this.__studyFilters = new osparc.component.filter.group.StudyFilterGroup("studyBrowser").set({
        paddingTop: 5
      });
      this._add(studyFilters);

      const studyBrowserLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(16));
      const tempStudyLayout = this.__createTemplateStudiesLayout();
      studyBrowserLayout.add(tempStudyLayout);
      const servicesLayout = this.__createServicesLayout();
      studyBrowserLayout.add(servicesLayout);
      const userStudyLayout = this.__createUserStudiesLayout();
      studyBrowserLayout.add(userStudyLayout);

      const scrollStudies = new qx.ui.container.Scroll();
      scrollStudies.add(studyBrowserLayout);
      this._add(scrollStudies, {
        flex: 1
      });
    },

    __createNewStudyButton: function() {
      const newStudyBtn = this.__newStudyBtn = new osparc.dashboard.StudyBrowserButtonNew();
      newStudyBtn.subscribeToFilterGroup("studyBrowser");
      osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
      newStudyBtn.addListener("execute", () => this.__createStudyBtnClkd());
      return newStudyBtn;
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

    __createUserStudiesLayout: function() {
      const userStudyContainer = this.__userStudyContainer = this.__createUserStudyList();
      const userStudyLayout = this.__createButtonsLayout(this.tr("Recent studies"), userStudyContainer);

      const studiesTitleContainer = userStudyLayout.getTitleBar();

      // Delete Studies Button
      const studiesDeleteButton = this.__createDeleteButton(false);
      studiesTitleContainer.add(new qx.ui.core.Spacer(20, null));
      studiesTitleContainer.add(studiesDeleteButton);
      userStudyContainer.addListener("changeSelection", e => {
        const nSelected = e.getData().length;
        this.__newStudyBtn.setEnabled(!nSelected);
        this.__userStudyContainer.getChildren().forEach(userStudyItem => {
          if (userStudyItem instanceof osparc.dashboard.StudyBrowserButtonItem) {
            userStudyItem.multiSelection(nSelected);
          }
        });
        this.__updateDeleteStudiesButton(studiesDeleteButton);
      }, this);

      return userStudyLayout;
    },

    __createTemplateStudiesLayout: function() {
      const resource = this.self().resources["templates"];
      const templateStudyContainer = this.__templateStudyContainer = this.__createTemplateStudyList();
      const tempStudyLayout = this.__createButtonsLayout(resource["label"], templateStudyContainer);

      const templatesTitleContainer = tempStudyLayout.getTitleBar();

      // Delete Templates Button
      const templateDeleteButton = this.__createDeleteButton(true);
      templatesTitleContainer.add(new qx.ui.core.Spacer(20, null));
      templatesTitleContainer.add(templateDeleteButton);
      templateStudyContainer.addListener("changeSelection", e => {
        const nSelected = e.getData().length;
        this.__templateStudyContainer.getChildren().forEach(templateStudyItem => {
          templateStudyItem.multiSelection(nSelected);
        });
        this.__updateDeleteTemplatesButton(templateDeleteButton);
      }, this);

      return tempStudyLayout;
    },

    __createServicesLayout: function() {
      const resource = this.self().resources["services"];
      const servicesContainer = this.__servicesContainer = this.__createServicesList();
      const servicesLayout = this.__createButtonsLayout(resource["label"], servicesContainer);
      return servicesLayout;
    },

    __getStudyAndStart: function(loadStudyId) {
      const params = {
        url: {
          projectId: loadStudyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this.__startStudy(studyData);
        })
        .catch(err => {
          if (osparc.data.Permissions.getInstance().getRole() === "Guest") {
            // If guest fails to load study, log him out
            osparc.auth.Manager.getInstance().logout();
          }
          console.error(err);
        });
    },

    __createDeleteButton: function(areTemplates) {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        visibility: "excluded"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteStudiesBtn");
      deleteButton.addListener("execute", () => {
        const selection = areTemplates ? this.__templateStudyContainer.getSelection() : this.__userStudyContainer.getSelection();
        const win = this.__createConfirmWindow(selection.length > 1);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), areTemplates)), areTemplates);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __attachEventHandlers: function() {
      const textfield = this.__studyFilters.getTextFilter().getChildControl("textfield");
      textfield.addListener("appear", () => {
        textfield.focus();
      }, this);
      const commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.__itemSelected(null);
      });
      osparc.store.Store.getInstance().addListener("changeTags", () => this.__resetStudyList(osparc.store.Store.getInstance().getStudies()), this);
    },

    __createStudyBtnClkd: function(templateData) {
      const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
      let title = templateData ? templateData.name : "New study";
      const existingTitles = this.__userStudies.map(study => study.name);
      if (existingTitles.includes(title)) {
        let cont = 1;
        while (existingTitles.includes(`${title} (${cont})`)) {
          cont++;
        }
        title += ` (${cont})`;
      }
      minStudyData["name"] = title;
      minStudyData["description"] = templateData ? templateData.description : "";
      this.__createStudy(minStudyData, templateData ? templateData.uuid : null);
    },

    __createStudyFromServiceBtnClkd: function(serviceKey) {
      this.__showLoadingPage(this.tr("Creating Study"));
      const store = osparc.store.Store.getInstance();
      store.getServicesDAGs()
        .then(services => {
          if (serviceKey in services) {
            const latestService = osparc.utils.Services.getLatest(services, serviceKey);
            const newUuid = osparc.utils.Utils.uuidv4();
            const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
            minStudyData["name"] = latestService["name"];
            minStudyData["workbench"] = {};
            minStudyData["workbench"][newUuid] = {
              "key": latestService["key"],
              "version": latestService["version"],
              "label": latestService["name"],
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
      this.__showLoadingPage(this.tr("Creating ") + (minStudyData.name || this.tr("Study")));
      if (templateId) {
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
      } else {
        const params = {
          data: minStudyData
        };
        osparc.data.Resources.fetch("studies", "post", params)
          .then(studyData => {
            this.__startStudy(studyData);
          })
          .catch(err => {
            console.error(err);
          });
      }
    },

    __startStudy: function(studyData) {
      this.__showLoadingPage(this.tr("Starting ") + (studyData.name || this.tr("Study")));
      osparc.store.Store.getInstance().getServicesDAGs()
        .then(() => {
          this.__hideLoadingPage();
          this.__loadStudy(studyData);
        });
    },

    __loadStudy: function(studyData) {
      const study = new osparc.data.model.Study(studyData);
      this.__studyEditor = this.__studyEditor || new osparc.desktop.StudyEditor();
      this.__studyEditor.setStudy(study);
      this.fireDataEvent("startStudy", this.__studyEditor);
    },

    __showStudiesLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    __createUserStudyList: function() {
      const usrLst = this.__userStudyContainer = this.__createStudyListLayout();
      osparc.utils.Utils.setIdToWidget(usrLst, "userStudiesList");
      return usrLst;
    },

    __createTemplateStudyList: function() {
      const tempList = this.__templateStudyContainer = this.__createStudyListLayout();
      osparc.utils.Utils.setIdToWidget(tempList, "templateStudiesList");
      return tempList;
    },

    __createServicesList: function() {
      const servicesList = this.__servicesContainer = this.__createStudyListLayout();
      osparc.utils.Utils.setIdToWidget(servicesList, "servicesList");
      return servicesList;
    },

    __resetStudyItem: function(studyData) {
      const userStudyList = this.__userStudies;
      const index = userStudyList.findIndex(userStudy => userStudy["uuid"] === studyData["uuid"]);
      if (index !== -1) {
        this.__userStudies[index] = studyData;
        this.__resetStudyList(userStudyList);
      }
    },

    __resetStudyList: function(userStudyList) {
      this.__userStudies = userStudyList;
      this.__userStudyContainer.removeAll();
      this.__userStudyContainer.add(this.__createNewStudyButton());
      this.self().sortStudyList(userStudyList);
      userStudyList.forEach(userStudy => {
        userStudy["resourceType"] = "study";
        this.__userStudyContainer.add(this.__createStudyItem(userStudy));
      });
      osparc.component.filter.UIFilterController.dispatch("studyBrowser");
    },

    __resetTemplateList: function(tempStudyList) {
      this.__templateStudies = tempStudyList;
      this.__templateStudyContainer.removeAll();
      this.self().sortStudyList(tempStudyList);
      tempStudyList.forEach(tempStudy => {
        tempStudy["resourceType"] = "template";
        this.__templateStudyContainer.add(this.__createStudyItem(tempStudy));
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

    __removeFromStudyList: function(studyId, isTemplate) {
      const studyContainer = isTemplate ? this.__templateStudyContainer: this.__userStudyContainer;
      const items = studyContainer.getChildren();
      for (let i=0; i<items.length; i++) {
        const item = items[i];
        if (item.getUuid && studyId === item.getUuid()) {
          studyContainer.remove(item);
          return;
        }
      }
    },

    __createStudyListLayout: function() {
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
        case "study":
          defaultThumbnail = "@FontAwesome5Solid/file-alt/50";
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
      item.subscribeToFilterGroup("studyBrowser");
      item.addListener("execute", () => {
        this.__itemClicked(item);
      }, this);

      return item;
    },

    __getStudyItemMenu: function(item, studyData) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const isTemplate = !(item.isResourceType("study"));

      const selectButton = this.__getSelectMenuButton(item, studyData, isTemplate);
      if (selectButton) {
        menu.add(selectButton);
      }

      const moreInfoButton = this.__getMoreInfoMenuButton(studyData, isTemplate);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      if (!isTemplate) {
        const shareStudyButton = this.__getPermissionsMenuButton(studyData);
        menu.add(shareStudyButton);

        const isCurrentUserOwner = this.__isUserOwner(studyData);
        const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
        if (isCurrentUserOwner && canCreateTemplate) {
          const saveAsTemplateButton = this.__getSaveAsTemplateMenuButton(studyData);
          menu.add(saveAsTemplateButton);
        }
      }

      const deleteButton = this.__getDeleteStudyMenuButton(studyData, isTemplate);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }

      return menu;
    },

    __getSelectMenuButton: function(item, studyData, isTemplate) {
      if (studyData["resourceType"] === "service") {
        return null;
      }
      const selectButton = new qx.ui.menu.Button(this.tr("Select"));
      selectButton.addListener("execute", () => {
        item.setValue(true);
        this.__itemMultiSelected(item, isTemplate);
      }, this);
      return selectButton;
    },

    __getMoreInfoMenuButton: function(studyData, isTemplate) {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        if (studyData["resourceType"] === "service") {
          const win = new osparc.component.metadata.ServiceInfoWindow(studyData);
          win.open();
          win.center();
        } else {
          const winWidth = 400;
          this.__createStudyDetailsEditor(studyData, isTemplate, winWidth);
        }
      }, this);
      return moreInfoButton;
    },

    __getPermissionsMenuButton: function(studyData) {
      const permissionsButton = new qx.ui.menu.Button(this.tr("Permissions"));
      permissionsButton.addListener("execute", () => {
        const permissionsView = new osparc.component.export.Permissions(studyData);
        permissionsView.addListener("updateStudy", e => {
          const studyId = e.getData();
          this.__reloadUserStudy(studyId);
        }, this);
        const window = permissionsView.createWindow();
        permissionsView.addListener("finished", e => {
          if (e.getData()) {
            window.close();
          }
        }, this);
        window.open();
      }, this);
      return permissionsButton;
    },

    __getSaveAsTemplateMenuButton: function(studyData) {
      const saveAsTemplateButton = new qx.ui.menu.Button(this.tr("Save as Template"));
      saveAsTemplateButton.addListener("execute", () => {
        const saveAsTemplateView = new osparc.component.export.SaveAsTemplate(studyData.uuid, studyData);
        const window = saveAsTemplateView.createWindow();
        saveAsTemplateView.addListener("finished", e => {
          const template = e.getData();
          if (template) {
            this.reloadTemplateStudies();
            window.close();
          }
        }, this);
        window.open();
      }, this);
      return saveAsTemplateButton;
    },

    __getDeleteStudyMenuButton: function(studyData, isTemplate) {
      const isCurrentUserOwner = this.__isUserOwner(studyData);
      if (isTemplate && !isCurrentUserOwner) {
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
            this.__deleteStudy(studyData, isTemplate);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __getStudyData: function(id, isTemplate) {
      const matchesId = study => study.uuid === id;
      return isTemplate ? this.__templateStudies.find(matchesId) : this.__userStudies.find(matchesId);
    },

    __itemClicked: function(item) {
      if (item.isResourceType("service")) {
        const serviceKey = item.getUuid();
        this.__createStudyFromServiceBtnClkd(serviceKey);
        this.__itemSelected(null);
        return;
      }
      const isTemplate = item.isResourceType("template");
      const selected = item.getValue();
      const studyData = this.__getStudyData(item.getUuid(), isTemplate);
      const studyContainer = isTemplate ? this.__templateStudyContainer : this.__userStudyContainer;

      const selection = studyContainer.getSelection();
      if (selection.length > 1) {
        this.__itemMultiSelected(item, isTemplate);
      } else if (selected) {
        isTemplate ? this.__createStudyBtnClkd(studyData) : this.__startStudy(studyData);
      }
    },

    __itemMultiSelected: function(item, isTemplate) {
      // Selection logic
      if (item.getValue()) {
        this.__itemSelected(item.getUuid());
      } else if (isTemplate) {
        const selection = this.__templateStudyContainer.getSelection();
        if (selection.length) {
          this.__itemSelected(selection[0].getUuid());
        } else {
          this.__itemSelected(null);
        }
      } else {
        const selection = this.__userStudyContainer.getSelection();
        if (selection.length) {
          this.__itemSelected(selection[0].getUuid());
        } else {
          this.__itemSelected(null);
        }
      }
    },

    __itemSelected: function(studyId) {
      if (studyId === null) {
        if (this.__userStudyContainer) {
          this.__userStudyContainer.resetSelection();
        }
        if (this.__templateStudyContainer) {
          this.__templateStudyContainer.resetSelection();
        }
        if (this.__servicesContainer) {
          this.__servicesContainer.resetSelection();
        }
      }
    },

    __createStudyDetailsEditor: function(studyData, isTemplate, winWidth) {
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(studyData, isTemplate, winWidth);
      studyDetails.addListener("updateStudy", () => this.reloadUserStudies(), this);
      studyDetails.addListener("updateTemplate", () => this.reloadTemplateStudies(), this);
      studyDetails.addListener("openStudy", () => {
        if (isTemplate) {
          this.__createStudyBtnClkd(studyData);
        } else {
          this.__startStudy(studyData);
        }
      }, this);
      studyDetails.addListener("updateTags", () => {
        if (isTemplate) {
          this.__resetTemplateList(osparc.store.Store.getInstance().getTemplates());
        } else {
          this.__resetStudyList(osparc.store.Store.getInstance().getStudies());
        }
      });

      const height = 400;
      const title = this.tr("Study Details Editor");
      const win = osparc.component.metadata.StudyDetailsEditor.popUpInWindow(title, studyDetails, winWidth, height);
      [
        "updateStudy",
        "updateTemplate",
        "openStudy"
      ].forEach(event => studyDetails.addListener(event, () => win.close()));
    },

    __updateDeleteStudiesButton: function(studiesDeleteButton) {
      const nSelected = this.__userStudyContainer.getSelection().length;
      if (nSelected) {
        studiesDeleteButton.setLabel(nSelected > 1 ? this.tr("Delete selected")+" ("+nSelected+")" : this.tr("Delete"));
        studiesDeleteButton.setVisibility("visible");
      } else {
        studiesDeleteButton.setVisibility("excluded");
      }
    },

    __updateDeleteTemplatesButton: function(templateDeleteButton) {
      const templateSelection = this.__templateStudyContainer.getSelection();
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
        })
        .finally(this.__itemSelected(null));
    },

    __deleteStudies: function(studiesData, areTemplates = false) {
      studiesData.forEach(studyData => {
        this.__deleteStudy(studyData, areTemplates);
      });
    },

    __createConfirmWindow: function(isMulti) {
      const msg = isMulti ? this.tr("Are you sure you want to delete the studies?") : this.tr("Are you sure you want to delete the study?");
      return new osparc.ui.window.Confirmation(msg);
    },

    __showLoadingPage: function(label) {
      this.__hideLoadingPage();

      this.__showStudiesLayout(false);

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

      this.__showStudiesLayout(true);
    },

    __isUserOwner: function(studyData) {
      const myEmail = osparc.auth.Data.getInstance().getEmail();
      if ("prjOwner" in studyData) {
        return studyData.prjOwner === myEmail;
      } else if ("getCreator" in studyData) {
        return studyData.getCreator() === myEmail;
      }
      return false;
    }
  }
});
