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
    }
  },

  members: {
    __loadingIFrame: null,
    __studyFilters: null,
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
    resetFilter: function() {
      if (this.__studyFilters) {
        this.__studyFilters.reset();
      }
    },

    __reloadUserStudy: function(studyId, reload) {
      osparc.store.Store.getInstance().getStudyWState(studyId, reload)
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
        osparc.store.Store.getInstance().getStudiesWState()
          .then(studies => {
            this.__resetStudyList(studies);
            this.resetSelection();
          })
          .catch(err => {
            console.error(err);
          });
      } else {
        this.__resetStudyList([]);
      }
    },

    __initResources: function() {
      this.__showLoadingPage(this.tr("Loading Studies"));

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
          this.__hideLoadingPage();
          this.__createStudiesLayout();
          this.__reloadResources();
          this.__attachEventHandlers();
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            this.__getStudyAndStart(loadStudyId);
          }
        })
        .catch(console.error);
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
            this.__startStudy(studyData);
          } else {
            osparc.store.Store.getInstance().setCurrentStudyId(null);
          }
        })
        .catch(err => {
          console.error(err);
        });
    },

    __createStudiesLayout: function() {
      const studyFilters = this.__studyFilters = new osparc.component.filter.group.StudyFilterGroup("studyBrowser").set({
        paddingTop: 5
      });
      this._add(studyFilters);

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
            userStudyItem.multiSelection(nSelected);
          }
        });
        this.__updateDeleteStudiesButton(studiesDeleteButton);
      }, this);

      return userStudyLayout;
    },

    __getStudyAndStart: function(loadStudyId) {
      osparc.store.Store.getStudyWState(loadStudyId, true)
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
          const studyItem = this.__userStudyContainer.getChildren().find(card => (card instanceof osparc.dashboard.StudyBrowserButtonItem) && (card.getUuid() === studyId));
          if (studyItem) {
            studyItem.setState(state);
          }
        }
      }, this);

      const textfield = this.__studyFilters.getTextFilter().getChildControl("textfield");
      textfield.addListener("appear", () => {
        textfield.focus();
      }, this);
      const commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.resetSelection();
      });
      osparc.store.Store.getInstance().addListener("changeTags", () => this.__resetStudyList(osparc.store.Store.getInstance().getStudies()), this);
    },

    __createStudyBtnClkd: function() {
      const minStudyData = osparc.data.model.Study.createMinimumStudyObject();
      let title = "New study";
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
      this.__showLoadingPage(this.tr("Creating ") + (minStudyData.name || this.tr("Study")));

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
    },

    __startStudy: function(studyData) {
      this.__showLoadingPage(this.tr("Starting ") + (studyData.name || this.tr("Study")));

      // Before starting a study, make sure the latest version is fetched
      const promises = [
        osparc.store.Store.getInstance().getStudyWState(studyData.uuid, true),
        osparc.store.Store.getInstance().getServicesDAGs()
      ];
      Promise.all(promises)
        .then(values => {
          this.__hideLoadingPage();
          studyData = values[0];
          this.__loadStudy(studyData);
        });
    },

    __loadStudy: function(studyData) {
      const study = new osparc.data.model.Study(studyData);
      this.fireDataEvent("startStudy", study);
    },

    __showStudiesLayout: function(show) {
      this._getChildren().forEach(children => {
        children.setVisibility(show ? "visible" : "excluded");
      });
    },

    __resetStudyItem: function(studyData) {
      const userStudyList = this.__userStudies;
      const index = userStudyList.findIndex(userStudy => userStudy["uuid"] === studyData["uuid"]);
      if (index === -1) {
        userStudyList.push(studyData);
      } else {
        userStudyList[index] = studyData;
      }
      this.__resetStudyList(userStudyList);
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

    __createStudyItem: function(study) {
      let defaultThumbnail = "";
      switch (study["resourceType"]) {
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
        state: study.state ? study.state : {},
        tags
      });
      const menu = this.__getStudyItemMenu(item, study);
      item.setMenu(menu);
      item.subscribeToFilterGroup("studyBrowser");
      item.addListener("execute", () => {
        if (!item.isLocked()) {
          this.__itemClicked(item);
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

      const moreInfoButton = this.__getMoreInfoMenuButton(studyData);
      if (moreInfoButton) {
        menu.add(moreInfoButton);
      }

      const shareStudyButton = this.__getPermissionsMenuButton(studyData);
      menu.add(shareStudyButton);

      const isCurrentUserOwner = this.__isUserOwner(studyData);
      const canCreateTemplate = osparc.data.Permissions.getInstance().canDo("studies.template.create");
      if (isCurrentUserOwner && canCreateTemplate) {
        const saveAsTemplateButton = this.__getSaveAsTemplateMenuButton(studyData);
        menu.add(saveAsTemplateButton);
      }

      const deleteButton = this.__getDeleteStudyMenuButton(studyData, false);
      if (deleteButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }

      return menu;
    },

    __getSelectMenuButton: function(item, studyData) {
      const selectButton = new qx.ui.menu.Button(this.tr("Select"));
      selectButton.addListener("execute", () => {
        item.setValue(true);
      }, this);
      return selectButton;
    },

    __getMoreInfoMenuButton: function(studyData) {
      const moreInfoButton = new qx.ui.menu.Button(this.tr("More Info"));
      moreInfoButton.addListener("execute", () => {
        const winWidth = 400;
        this.__createStudyDetailsEditor(studyData, winWidth);
      }, this);
      return moreInfoButton;
    },

    __getPermissionsMenuButton: function(studyData) {
      const permissionsButton = new qx.ui.menu.Button(this.tr("Permissions"));
      permissionsButton.addListener("execute", () => {
        const permissionsView = new osparc.component.export.Permissions(studyData);
        permissionsView.addListener("updateStudy", e => {
          const studyId = e.getData();
          this.__reloadUserStudy(studyId, true);
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
            console.log("templates should be reloaded");
            window.close();
          }
        }, this);
        window.open();
      }, this);
      return saveAsTemplateButton;
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

    __itemClicked: function(item) {
      const selected = item.getValue();
      const selection = this.__userStudyContainer.getSelection();
      if (selected && selection.length === 1) {
        const studyData = this.__getStudyData(item.getUuid(), false);
        this.__startStudy(studyData);
      }
    },

    __createStudyDetailsEditor: function(studyData, winWidth) {
      const studyDetails = new osparc.component.metadata.StudyDetailsEditor(studyData, false, winWidth);
      studyDetails.addListener("updateStudy", () => this.reloadUserStudies(), this);
      studyDetails.addListener("openStudy", () => {
        this.__startStudy(studyData);
      }, this);
      studyDetails.addListener("updateTags", () => {
        this.__resetStudyList(osparc.store.Store.getInstance().getStudies());
      });

      const height = 400;
      const title = this.tr("Study Details Editor");
      const win = osparc.component.metadata.StudyDetailsEditor.popUpInWindow(title, studyDetails, winWidth, height);
      [
        "updateStudy",
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

    __deleteStudy: function(studyData) {
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
        operationPromise = osparc.data.Resources.fetch("studies", "put", params);
      } else {
        // delete study
        operationPromise = osparc.data.Resources.fetch("studies", "delete", params, studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromStudyList(studyData.uuid, false))
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
