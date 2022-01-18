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

qx.Class.define("osparc.dashboard.TemplateBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  members: {
    __templates: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "scroll-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          control.getChildControl("pane").addListener("scrollY", () => this._moreStudiesRequired(), this);
          break;
        case "templates-layout": {
          const scroll = this.getChildControl("scroll-container");
          control = this.__createTemplatesLayout();
          scroll.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this._resourcesContainer) {
        this._resourcesContainer.resetSelection();
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

    // overridden
    _initResources: function() {
      this._showLoadingPage(this.tr("Starting..."));

      this.__templates = [];
      const resourcePromises = [];
      const store = osparc.store.Store.getInstance();
      resourcePromises.push(store.getServicesDAGs(true));
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        resourcePromises.push(osparc.data.Resources.get("tags"));
      }

      Promise.all(resourcePromises)
        .then(() => {
          this.getChildControl("templates-layout");
          this.__reloadResources();
          this._hideLoadingPage();
        })
        .catch(console.error);
    },

    // overridden
    _showMainLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    __reloadResources: function() {
      this.reloadStudies();
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
      const templatesLayout = this._createResourcesLayout();

      osparc.utils.Utils.setIdToWidget(this._resourcesContainer, "templateStudiesList");

      const loadingTemplatesBtn = this._createLoadMoreButton("templatesLoading");
      this._resourcesContainer.add(loadingTemplatesBtn);

      this._resourcesContainer.addListener("changeVisibility", () => this._moreStudiesRequired());
      this._resourcesContainer.addListener("changeMode", () => this._resetTemplatesList());

      return templatesLayout;
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
      const loadMoreCard = this._resourcesContainer.getChildren().find(el => el === this._loadingResourcesBtn);
      if (loadMoreCard) {
        loadMoreFetching = loadMoreCard.getFetching();
        loadMoreVisibility = loadMoreCard.getVisibility();
      }

      this._resourcesContainer.removeAll();

      osparc.dashboard.ResourceBrowserBase.sortStudyList(tempStudyList);
      tempStudyList.forEach(tempStudy => {
        tempStudy["resourceType"] = "template";
        const templateItem = this.__createStudyItem(tempStudy, this._resourcesContainer.getMode());
        templateItem.addListener("updateQualityTemplate", e => {
          const updatedTemplateData = e.getData();
          updatedTemplateData["resourceType"] = "template";
          this._resetTemplateItem(updatedTemplateData);
        }, this);
        this._resourcesContainer.add(templateItem);
      });

      if (loadMoreCard) {
        const newLoadMoreBtn = this._createLoadMoreButton("templatesLoading", this._resourcesContainer.getMode());
        newLoadMoreBtn.set({
          fetching: loadMoreFetching,
          visibility: loadMoreVisibility
        });
        this._resourcesContainer.add(newLoadMoreBtn);
      }

      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    _addStudiesToList: function(newTemplatesList) {
      osparc.dashboard.ResourceBrowserBase.sortStudyList(newTemplatesList);
      const templatesList = this._resourcesContainer.getChildren();
      newTemplatesList.forEach(template => {
        if (this.__templates.indexOf(template) === -1) {
          this.__templates.push(template);
        }

        template["resourceType"] = "template";
        const idx = templatesList.findIndex(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === template["uuid"]);
        if (idx !== -1) {
          return;
        }
        const templateItem = this.__createStudyItem(template, this._resourcesContainer.getMode());
        this._resourcesContainer.add(templateItem);
      });
      osparc.dashboard.ResourceBrowserBase.sortStudyList(templatesList.filter(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)));
      const idx = templatesList.findIndex(card => card instanceof osparc.dashboard.GridButtonLoadMore);
      if (idx !== -1) {
        templatesList.push(templatesList.splice(idx, 1)[0]);
      }
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    __removeFromStudyList: function(studyId) {
      const studyContainer = this._resourcesContainer;
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
      this._resourcesContainer.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
      this._resourcesContainer.setMode(mode);
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

      const qualityButton = this.__getQualityMenuButton(studyData);
      if (qualityButton) {
        menu.add(qualityButton);
      }

      const classifiersButton = this.__getClassifiersMenuButton(studyData);
      if (classifiersButton) {
        menu.add(classifiersButton);
      }

      const studyServicesButton = this.__getStudyServicesMenuButton(studyData);
      menu.add(studyServicesButton);

      const publishOnPortalButton = this.__getPublishOnPortalMenuButton(studyData);
      if (publishOnPortalButton) {
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
      if (osparc.data.model.Study.isOwner(studyData)) {
        const permissionsButton = new qx.ui.menu.Button(this.tr("Sharing"));
        permissionsButton.addListener("execute", () => {
          this.__openPermissions(studyData);
        }, this);
        return permissionsButton;
      }
      return null;
    },

    __getQualityMenuButton: function(studyData) {
      if (osparc.data.model.Study.isOwner(studyData) && "quality" in studyData) {
        const qualityMenuButton = this._getQualityMenuButton(studyData);
        return qualityMenuButton;
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
      const studyServicesButton = new qx.ui.menu.Button(this.tr("Services"));
      studyServicesButton.addListener("execute", () => {
        const servicesInStudy = new osparc.component.metadata.ServicesInStudy(studyData);
        const title = this.tr("Services in Study");
        osparc.ui.window.Window.popUpInWindow(servicesInStudy, title, 650, 300);
      }, this);
      return studyServicesButton;
    },

    __getPublishOnPortalMenuButton: function(studyData) {
      if (osparc.data.model.Study.isOwner(studyData)) {
        const publishOnPortalButton = new qx.ui.menu.Button(this.tr("Publish on Portal"));
        publishOnPortalButton.addListener("execute", () => {
          const msg = this.tr("Not yet implemented");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "INFO");
        }, this);
        return publishOnPortalButton;
      }
      return null;
    },

    __getDeleteTemplateMenuButton: function(studyData) {
      const isCurrentUserOwner = osparc.data.model.Study.isOwner(studyData);
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
      const matchesId = study => study.uuid === item.getUuid();
      const templateData = this.__templates.find(matchesId);
      this._createStudyFromTemplate(templateData);
      this.resetSelection();
    },

    __openPermissions: function(studyData) {
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
          this._resetTemplateItem(updatedResource);
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
    }
  }
});
