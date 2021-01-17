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
 *   let prjBrowser = this.__serviceBrowser = new osparc.dashboard.StudyBrowser();
 *   this.getRoot().add(prjBrowser);
 * </pre>
 */

qx.Class.define("osparc.dashboard.StudyBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  events: {
    "updateTemplates": "qx.event.type.Event"
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
    }
  },

  members: {
    __userStudyContainer: null,
    __userStudies: null,
    __newStudyBtn: null,

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this.__userStudyContainer) {
        this.__userStudyContainer.resetSelection();
      }
    },

    _reloadStudy: function(studyId) {
      const params = {
        url: {
          "projectId": studyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this._resetStudyItem(studyData);
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
        return new Promise((resolve, reject) => {
          osparc.data.Resources.get("studies", null, false)
            .then(studies => {
              studies.forEach(study => {
                osparc.component.metadata.Quality.attachQualityToObject(study);
              });
              this._resetStudiesList(studies);
              this.resetSelection();
              resolve(studies);
            })
            .catch(err => {
              console.error(err);
              reject(err);
            });
        });
      }
      this._resetStudiesList([]);
      return null;
    },

    // overriden
    _initResources: function() {
      this._showLoadingPage(this.tr("Loading Studies"));

      this.__userStudies = [];
      const resourcePromises = [];
      const store = osparc.store.Store.getInstance();
      resourcePromises.push(store.getVisibleMembers());
      resourcePromises.push(store.getServicesDAGs(true));
      if (osparc.data.Permissions.getInstance().canDo("study.tag")) {
        resourcePromises.push(osparc.data.Resources.get("tags"));
      }
      Promise.all(resourcePromises)
        .then(() => {
          this.__createStudiesLayout();
          this.__reloadResources();
          this.__attachEventHandlers();
          this._hideLoadingPage();
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            this.__getStudyAndStart(loadStudyId);
          }
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
      this.__getActiveStudy();
      this.reloadUserStudies();
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
            this._startStudy(studyData["uuid"]);
          } else {
            osparc.store.Store.getInstance().setCurrentStudyId(null);
          }
        })
        .catch(err => {
          console.error(err);
        });
    },

    __createStudiesLayout: function() {
      const studyBrowserLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(16));
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
      newStudyBtn.subscribeToFilterGroup("sideSearchFilter");
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
      const userStudyContainer = this.__userStudyContainer = this.__createStudyListLayout();
      osparc.utils.Utils.setIdToWidget(userStudyContainer, "userStudiesList");
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
            userStudyItem.setMultiSelectionMode(Boolean(nSelected));
          }
        });
        this.__updateDeleteStudiesButton(studiesDeleteButton);
      }, this);

      return userStudyLayout;
    },

    __getStudyAndStart: function(loadStudyId) {
      const params = {
        url: {
          "projectId": loadStudyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this._startStudy(studyData["uuid"]);
        });
    },

    __createDeleteButton: function() {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        visibility: "excluded"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteStudiesBtn");
      deleteButton.addListener("execute", () => {
        const selection = this.__userStudyContainer.getSelection();
        const win = this.__createConfirmWindow(selection.length > 1);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __studyStateReceived: function(studyId, state) {
      const studyItem = this.__userStudyContainer.getChildren().find(card => (card instanceof osparc.dashboard.StudyBrowserButtonItem) && (card.getUuid() === studyId));
      if (studyItem) {
        studyItem.setState(state);
      }
      osparc.store.Store.getInstance().setStudyState(studyId, state);
    },

    __attachEventHandlers: function() {
      // Listen to socket
      const socket = osparc.wrapper.WebSocket.getInstance();
      // callback for incoming logs
      const slotName = "projectStateUpdated";
      socket.removeSlot(slotName);
      socket.on(slotName, function(jsonString) {
        const data = JSON.parse(jsonString);
        if (data) {
          const studyId = data["project_uuid"];
          const state = ("data" in data) ? data["data"] : {};
          this.__studyStateReceived(studyId, state);
        }
      }, this);

      const commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.resetSelection();
      });
      osparc.store.Store.getInstance().addListener("changeTags", () => {
        if (osparc.auth.Manager.getInstance().isLoggedIn()) {
          this.reloadUserStudies();
        }
      }, this);
    },

    __createStudyBtnClkd: function() {
      const minStudyData = osparc.data.model.Study.createMyNewStudyObject();
      let title = minStudyData.name;
      const existingTitles = this.__userStudies.map(study => study.name);
      if (existingTitles.includes(title)) {
        let cont = 1;
        while (existingTitles.includes(`${title} (${cont})`)) {
          cont++;
        }
        title += ` (${cont})`;
      }
      minStudyData["name"] = title;
      minStudyData["description"] = "";
      this.__createStudy(minStudyData, null);
    },

    __createStudy: function(minStudyData) {
      this._showLoadingPage(this.tr("Creating ") + (minStudyData.name || this.tr("Study")));

      const params = {
        data: minStudyData
      };
      osparc.data.Resources.fetch("studies", "post", params)
        .then(studyData => {
          this._hideLoadingPage();
          this._startStudy(studyData["uuid"]);
        })
        .catch(err => {
          console.error(err);
        });
    },

    _startStudy: function(studyId, pageContext) {
      const data = {
        studyId,
        pageContext
      };
      this.fireDataEvent("startStudy", data);
    },

    _resetStudyItem: function(studyData) {
      const userStudiesList = this.__userStudies;
      const index = userStudiesList.findIndex(userStudy => userStudy["uuid"] === studyData["uuid"]);
      if (index === -1) {
        userStudiesList.push(studyData);
      } else {
        userStudiesList[index] = studyData;
      }
      this._resetStudiesList(userStudiesList);
    },

    _resetStudiesList: function(userStudiesList) {
      this.__userStudies = userStudiesList;
      this.__userStudyContainer.removeAll();
      this.__userStudyContainer.add(this.__createNewStudyButton());
      this.self().sortStudyList(userStudiesList);
      userStudiesList.forEach(userStudy => {
        userStudy["resourceType"] = "study";
        // do not add secondary studies to the list
        if (osparc.data.model.Study.isStudySecondary(userStudy)) {
          return;
        }
        this.__userStudyContainer.add(this.__createStudyItem(userStudy));
      });
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    __removeFromStudyList: function(studyId) {
      const studyContainer = this.__userStudyContainer;
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

    __createStudyItem: function(studyData) {
      const tags = studyData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => studyData.tags.includes(tag.id)) : [];
      const item = new osparc.dashboard.StudyBrowserButtonItem().set({
        resourceData: studyData,
        tags
      });

      const menu = this.__getStudyItemMenu(item, studyData);
      item.setMenu(menu);
      item.subscribeToFilterGroup("sideSearchFilter");
      item.addListener("tap", e => {
        if (!item.isLocked()) {
          this.__itemClicked(item, e.getNativeEvent().shiftKey);
        }
      }, this);

      return item;
    },

    __getStudyItemMenu: function(item, studyData) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const selectButton = this.__getSelectMenuButton(item, studyData);
      if (selectButton) {
        menu.add(selectButton);
      }

      const moreInfoButton = this._getMoreInfoMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      if ("quality" in studyData) {
        const qualityButton = this._getQualityMenuButton(studyData);
        menu.add(qualityButton);
      }

      const classifiersButton = this.__getClassifiersMenuButton(studyData);
      if (classifiersButton) {
        menu.add(classifiersButton);
      }

      const shareStudyButton = this.__getPermissionsMenuButton(studyData);
      menu.add(shareStudyButton);

      const studyServicesButton = this.__getStudyServicesMenuButton(studyData);
      menu.add(studyServicesButton);

      const isCurrentUserOwner = osparc.data.model.Study.isOwner(studyData);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (isCurrentUserOwner && canCreateTemplate) {
        const saveAsTemplateButton = this.__getSaveAsTemplateMenuButton(studyData);
        menu.add(saveAsTemplateButton);
      }

      if (osparc.data.model.Study.hasSlideshow(studyData) && osparc.data.Permissions.getInstance().canDo("study.slides")) {
        const startAsSlideshowButton = this.__getStartAsSlideshowButton(studyData);
        menu.add(startAsSlideshowButton);
      }

      const deleteButton = this.__getDeleteStudyMenuButton(studyData, false);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }

      return menu;
    },

    __getSelectMenuButton: function(item) {
      const selectButton = new qx.ui.menu.Button(this.tr("Select"));
      selectButton.addListener("execute", () => {
        item.setValue(true);
        this.__userStudyContainer.setLastSelectedItem(item);
      }, this);
      return selectButton;
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

    __openClassifiers: function(studyData) {
      const classifiersEditor = new osparc.dashboard.ClassifiersEditor(studyData);
      const title = this.tr("Classifiers");
      osparc.ui.window.Window.popUpInWindow(classifiersEditor, title, 400, 400);
      classifiersEditor.addListener("updateResourceClassifiers", e => {
        const studyId = e.getData();
        this._reloadStudy(studyId);
      }, this);
    },

    __getPermissionsMenuButton: function(studyData) {
      const permissionsButton = new qx.ui.menu.Button(this.tr("Permissions"));
      permissionsButton.addListener("execute", () => {
        const permissionsView = new osparc.component.export.StudyPermissions(studyData);
        const title = this.tr("Share with Collaborators and Organizations");
        osparc.ui.window.Window.popUpInWindow(permissionsView, title, 400, 300);
        permissionsView.addListener("updateStudy", e => {
          const studyId = e.getData();
          this._reloadStudy(studyId);
        }, this);
      }, this);
      return permissionsButton;
    },

    __getStudyServicesMenuButton: function(studyData) {
      const studyServicesButton = new qx.ui.menu.Button(this.tr("Services"));
      studyServicesButton.addListener("execute", () => {
        const servicesInStudy = new osparc.component.metadata.ServicesInStudy(studyData);
        const title = this.tr("Services in Study");
        osparc.ui.window.Window.popUpInWindow(servicesInStudy, title, 400, 100);
      }, this);
      return studyServicesButton;
    },

    __getSaveAsTemplateMenuButton: function(studyData) {
      const saveAsTemplateButton = new qx.ui.menu.Button(this.tr("Publish as Template"));
      saveAsTemplateButton.addListener("execute", () => {
        const saveAsTemplateView = new osparc.component.export.SaveAsTemplate(studyData.uuid, studyData);
        const title = this.tr("Publish as Template");
        const window = osparc.ui.window.Window.popUpInWindow(saveAsTemplateView, title, 400, 300);
        saveAsTemplateView.addListener("finished", e => {
          const template = e.getData();
          if (template) {
            this.fireEvent("updateTemplates");
            window.close();
          }
        }, this);
      }, this);
      return saveAsTemplateButton;
    },

    __getStartAsSlideshowButton: function(studyData) {
      const startAsSlideshowButton = new qx.ui.menu.Button(this.tr("Start Guided mode"));
      startAsSlideshowButton.addListener("execute", () => {
        this._startStudy(studyData["uuid"], "slideshow");
      }, this);
      return startAsSlideshowButton;
    },

    __getDeleteStudyMenuButton: function(studyData) {
      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => {
        const win = this.__createConfirmWindow(false);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__deleteStudy(studyData);
          }
        }, this);
      }, this);
      return deleteButton;
    },

    __getStudyData: function(id) {
      const matchesId = study => study.uuid === id;
      return this.__userStudies.find(matchesId);
    },

    __itemClicked: function(item, isShiftPressed) {
      const studiesCont = this.__userStudyContainer;
      const selected = item.getValue();
      const selection = studiesCont.getSelection();

      if (isShiftPressed) {
        const lastIdx = studiesCont.getLastSelectedIndex();
        const currentIdx = studiesCont.getIndex(item);
        const minMaxIdx = [lastIdx, currentIdx].sort();
        for (let i=minMaxIdx[0]; i<=minMaxIdx[1]; i++) {
          const button = studiesCont.getChildren()[i];
          button.setValue(true);
        }
      }
      studiesCont.setLastSelectedIndex(studiesCont.getIndex(item));

      if (selected && selection.length === 1) {
        const studyData = this.__getStudyData(item.getUuid(), false);
        this._startStudy(studyData["uuid"]);
      }
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

    __deleteStudy: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        // remove collaborator
        osparc.component.export.StudyPermissions.removeCollaborator(studyData, myGid);
        const params = {
          url: {
            projectId: studyData.uuid
          }
        };
        params["data"] = studyData;
        operationPromise = osparc.data.Resources.fetch("studies", "put", params);
      } else {
        // delete study
        operationPromise = osparc.store.Store.getInstance().deleteStudy(studyData.uuid);
      }
      operationPromise
        .then(() => {
          this.__deleteSecondaryStudies(studyData);
          this.__removeFromStudyList(studyData.uuid, false);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(this.resetSelection());
    },

    __deleteStudies: function(studiesData) {
      studiesData.forEach(studyData => {
        this.__deleteStudy(studyData);
      });
    },

    __deleteSecondaryStudies: function(studyData) {
      if ("dev" in studyData && "sweeper" in studyData["dev"] && "secondaryStudyIds" in studyData["dev"]["sweeper"]) {
        const secondaryStudyIds = studyData["dev"]["sweeper"]["secondaryStudyIds"];
        secondaryStudyIds.forEach(secondaryStudyId => {
          osparc.store.Store.getInstance().deleteStudy(secondaryStudyId);
        });
      }
    },

    __createConfirmWindow: function(isMulti) {
      const msg = isMulti ? this.tr("Are you sure you want to delete the studies?") : this.tr("Are you sure you want to delete the study?");
      return new osparc.ui.window.Confirmation(msg);
    }
  }
});
