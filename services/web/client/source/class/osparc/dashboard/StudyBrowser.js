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

  members: {
    __userStudies: null,
    __newStudyBtn: null,

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
        case "studies-layout": {
          const scroll = this.getChildControl("scroll-container");
          control = this.__createUserStudiesLayout();
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
      if (this._studiesContainer) {
        this._studiesContainer.resetSelection();
      }
    },

    reloadStudy: function(studyId) {
      const params = {
        url: {
          "studyId": studyId
        }
      };
      return osparc.data.Resources.getOne("studies", params)
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
    reloadStudies: function() {
      if (osparc.data.Permissions.getInstance().canDo("studies.user.read")) {
        this._requestStudies(false);
      } else {
        this._resetStudiesList([]);
      }
    },

    invalidateStudies: function() {
      osparc.store.Store.getInstance().invalidate("studies");
      this._resetStudiesList([]);
      this._studiesContainer.nextRequest = null;
    },

    // overriden
    _initResources: function() {
      this._showLoadingPage(this.tr("Starting..."));

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
          this.getChildControl("studies-layout");
          this.__reloadResources();
          this.__attachEventHandlers();
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            this.__getStudyAndStart(loadStudyId);
          }
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
      this.__getActiveStudy();
      this.reloadStudies();
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
            this._startStudy(studyData);
          } else {
            osparc.store.Store.getInstance().setCurrentStudyId(null);
          }
        })
        .catch(err => {
          console.error(err);
        });
    },

    __createNewStudyButton: function(mode = "grid") {
      const newStudyBtn = this.__newStudyBtn = (mode === "grid") ? new osparc.dashboard.GridButtonNew() : new osparc.dashboard.ListButtonNew();
      newStudyBtn.subscribeToFilterGroup("sideSearchFilter");
      osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
      newStudyBtn.addListener("execute", () => this.__createStudyBtnClkd());
      return newStudyBtn;
    },

    __createLoadMoreStudiesButton: function(mode = "grid") {
      const loadingStudiesBtn = this._loadingStudiesBtn = (mode === "grid") ? new osparc.dashboard.GridButtonLoadMore() : new osparc.dashboard.ListButtonLoadMore();
      osparc.utils.Utils.setIdToWidget(loadingStudiesBtn, "studiesLoading");
      return loadingStudiesBtn;
    },

    __createCollapsibleView: function(title) {
      const userStudyLayout = new osparc.component.widget.CollapsibleView(title);
      userStudyLayout.getChildControl("title").set({
        font: "title-16"
      });
      userStudyLayout._getLayout().setSpacing(8); // eslint-disable-line no-underscore-dangle
      return userStudyLayout;
    },

    __createUserStudiesLayout: function() {
      const userStudyLayout = this.__createCollapsibleView(this.tr("Recent studies"));

      const titleBarBtnsContainerLeft = userStudyLayout.getTitleBarBtnsContainerLeft();
      const importStudyButton = this.__createImportButton();
      titleBarBtnsContainerLeft.add(importStudyButton);
      const studiesDeleteButton = this.__createDeleteButton(false);
      titleBarBtnsContainerLeft.add(studiesDeleteButton);

      const titleBarBtnsContainerRight = userStudyLayout.getTitleBarBtnsContainerRight();
      const viewGridBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/apps/18");
      titleBarBtnsContainerRight.add(viewGridBtn);
      const viewListBtn = new qx.ui.form.ToggleButton(null, "@MaterialIcons/reorder/18");
      titleBarBtnsContainerRight.add(viewListBtn);
      const group = new qx.ui.form.RadioGroup();
      group.add(viewGridBtn);
      group.add(viewListBtn);

      const userStudyContainer = this._studiesContainer = this.__createStudiesContainer();
      userStudyLayout.setContent(userStudyContainer);
      osparc.utils.Utils.setIdToWidget(userStudyContainer, "userStudiesList");

      const newStudyButton = this.__createNewStudyButton();
      userStudyContainer.add(newStudyButton);

      const loadingStudiesBtn = this.__createLoadMoreStudiesButton();
      userStudyContainer.add(loadingStudiesBtn);

      viewGridBtn.addListener("execute", () => {
        this.__setStudiesContainerMode("grid");
      });
      viewListBtn.addListener("execute", () => {
        this.__setStudiesContainerMode("list");
      });

      userStudyContainer.addListener("changeSelection", e => {
        const nSelected = e.getData().length;
        this._studiesContainer.getChildren().forEach(userStudyItem => {
          if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(userStudyItem)) {
            userStudyItem.setMultiSelectionMode(Boolean(nSelected));
          }
        });
      }, this);
      userStudyContainer.bind("selection", this.__newStudyBtn, "enabled", {
        converter: selection => !selection.length
      });
      userStudyContainer.bind("selection", importStudyButton, "enabled", {
        converter: selection => !selection.length
      });
      userStudyContainer.bind("selection", studiesDeleteButton, "visibility", {
        converter: selection => selection.length ? "visible" : "excluded"
      });
      userStudyContainer.bind("selection", studiesDeleteButton, "label", {
        converter: selection => selection.length > 1 ? this.tr("Delete selected")+" ("+selection.length+")" : this.tr("Delete")
      });

      userStudyContainer.addListener("changeVisibility", () => this._moreStudiesRequired());

      userStudyContainer.addListener("changeMode", () => {
        this._resetStudiesList();

        const userStudyItems = this._studiesContainer.getChildren();
        userStudyItems.forEach((userStudyItem, i) => {
          if (!osparc.dashboard.ResourceBrowserBase.isCardButtonItem(userStudyItem)) {
            if (userStudyItem === this.__newStudyBtn) {
              this._studiesContainer.remove(userStudyItem);
              const newBtn = this.__createNewStudyButton(this._studiesContainer.getMode());
              this._studiesContainer.addAt(newBtn, i);
              if (this._studiesContainer.getMode() === "list") {
                const width = this._studiesContainer.getBounds().width - 15;
                newBtn.setWidth(width);
              }
            }

            if (userStudyItem === this._loadingStudiesBtn) {
              const fetching = userStudyItem.getFetching();
              const visibility = userStudyItem.getVisibility();
              this._studiesContainer.remove(userStudyItem);
              const loadMoreBtn = this.__createLoadMoreStudiesButton(this._studiesContainer.getMode());
              loadMoreBtn.set({
                fetching,
                visibility
              });
              this._studiesContainer.add(loadMoreBtn);
            }
          }
        });
      }, this);

      return userStudyLayout;
    },

    __getStudyAndStart: function(loadStudyId) {
      const params = {
        url: {
          "studyId": loadStudyId
        }
      };
      osparc.data.Resources.getOne("studies", params)
        .then(studyData => {
          this._startStudy(studyData);
        })
        .catch(() => {
          const msg = this.tr("Study unavailable or inaccessible");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
    },

    __createImportButton: function() {
      const importButton = new qx.ui.form.Button(this.tr("Import"));
      importButton.addListener("execute", () => {
        const importStudy = new osparc.component.study.Import();
        const win = osparc.ui.window.Window.popUpInWindow(importStudy, this.tr("Import Study"), 400, 125);
        win.set({
          clickAwayClose: false
        });
        importStudy.addListener("fileReady", e => {
          win.close();
          const file = e.getData();
          if (file === null || file === undefined) {
            return;
          }
          const size = file.size;
          const maxSize = 10 * 1024 * 1024 * 1024; // 10 GB
          if (size > maxSize) {
            osparc.component.message.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          this.__importStudy(file);
        }, this);
      }, this);
      return importButton;
    },

    __createDeleteButton: function() {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        visibility: "excluded"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteStudiesBtn");
      deleteButton.addListener("execute", () => {
        const selection = this._studiesContainer.getSelection();
        const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
        if (preferencesSettings.getConfirmDeleteStudy()) {
          const win = this.__createConfirmWindow(selection.length > 1);
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__deleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
            }
          }, this);
        } else {
          this.__deleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
        }
      }, this);
      return deleteButton;
    },

    __studyStateReceived: function(studyId, state) {
      osparc.store.Store.getInstance().setStudyState(studyId, state);
      const idx = this.__userStudies.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this.__userStudies[idx]["state"] = state;
      }
      const studyItem = this._studiesContainer.getChildren().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === studyId);
      if (studyItem) {
        studyItem.setState(state);
      }
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
        this.invalidateStudies();
        this.reloadStudies();
      }, this);
    },

    __createStudyBtnClkd: function() {
      this.__newStudyBtn.setValue(false);
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
          this._startStudy(studyData);
        })
        .catch(err => {
          console.error(err);
        });
    },

    _startStudy: function(studyData, pageContext) {
      if (pageContext === undefined) {
        pageContext = osparc.data.model.Study.getUiMode(studyData) || "workbench";
      }
      const studyId = studyData["uuid"];
      const data = {
        studyId,
        pageContext
      };
      this.fireDataEvent("startStudy", data);
    },

    _resetStudyItem: function(studyData) {
      const userStudies = this.__userStudies;
      const index = userStudies.findIndex(userStudy => userStudy["uuid"] === studyData["uuid"]);
      if (index === -1) {
        userStudies.push(studyData);
      } else {
        userStudies[index] = studyData;
      }
      this._resetStudiesList(userStudies);
    },

    _resetStudiesList: function(userStudiesList) {
      if (userStudiesList === undefined) {
        userStudiesList = this.__userStudies;
      }
      const userStudyItems = this._studiesContainer.getChildren();
      for (let i=userStudyItems.length-1; i>=0; i--) {
        const userStudyItem = userStudyItems[i];
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(userStudyItem)) {
          this._studiesContainer.remove(userStudyItem);
        }
      }
      this._addStudiesToList(userStudiesList);
    },

    _addStudiesToList: function(userStudiesList) {
      osparc.dashboard.ResourceBrowserBase.sortStudyList(userStudiesList);
      const studyList = this._studiesContainer.getChildren();
      userStudiesList.forEach(userStudy => {
        if (this.__userStudies.indexOf(userStudy) === -1) {
          this.__userStudies.push(userStudy);
        }

        userStudy["resourceType"] = "study";
        // do not add secondary studies to the list
        if (osparc.data.model.Study.isStudySecondary(userStudy)) {
          return;
        }
        const idx = studyList.findIndex(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === userStudy["uuid"]);
        if (idx !== -1) {
          return;
        }
        const studyItem = this.__createStudyItem(userStudy);
        this._studiesContainer.add(studyItem);
      });
      osparc.dashboard.ResourceBrowserBase.sortStudyList(studyList.filter(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)));
      const idx = studyList.findIndex(card => (card instanceof osparc.dashboard.GridButtonLoadMore) || (card instanceof osparc.dashboard.ListButtonLoadMore));
      if (idx !== -1) {
        studyList.push(studyList.splice(idx, 1)[0]);
      }
      osparc.component.filter.UIFilterController.dispatch("sideSearchFilter");
    },

    __removeFromStudyList: function(studyId) {
      const idx = this.__userStudies.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this.__userStudies.splice(idx, 1);
      }
      const studyItem = this._studiesContainer.getChildren().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === studyId);
      if (studyItem) {
        this._studiesContainer.remove(studyItem);
      }
    },

    __createStudiesContainer: function() {
      const spacing = osparc.dashboard.GridButtonBase.SPACING;
      return new osparc.component.form.ToggleButtonContainer(new qx.ui.layout.Flow(spacing, spacing));
    },

    __setStudiesContainerMode: function(mode = "grid") {
      const spacing = mode === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
      this._studiesContainer.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
      this._studiesContainer.setMode(mode);
    },

    __createStudyItem: function(studyData) {
      const tags = studyData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => studyData.tags.includes(tag.id)) : [];

      const item = this._studiesContainer.getMode() === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      item.set({
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
      item.addListener("updateQualityStudy", e => {
        const updatedStudyData = e.getData();
        updatedStudyData["resourceType"] = "study";
        this._resetStudyItem(updatedStudyData);
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

      const shareStudyButton = this.__getPermissionsMenuButton(studyData);
      menu.add(shareStudyButton);

      if ("quality" in studyData) {
        const qualityButton = this._getQualityMenuButton(studyData);
        menu.add(qualityButton);
      }

      const classifiersButton = this.__getClassifiersMenuButton(studyData);
      if (classifiersButton) {
        menu.add(classifiersButton);
      }

      const studyServicesButton = this.__getStudyServicesMenuButton(studyData);
      menu.add(studyServicesButton);

      const duplicateStudyButton = this.__getDuplicateStudyMenuButton(studyData);
      menu.add(duplicateStudyButton);

      const exportButton = this.__getExportMenuButton(studyData);
      menu.add(exportButton);

      const isCurrentUserOwner = osparc.data.model.Study.isOwner(studyData);
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

    __getSelectMenuButton: function(item) {
      const selectButton = new qx.ui.menu.Button(this.tr("Select"));
      selectButton.addListener("execute", () => {
        item.setValue(true);
        this._studiesContainer.setLastSelectedItem(item);
      }, this);
      return selectButton;
    },

    __getPermissionsMenuButton: function(studyData) {
      const permissionsButton = new qx.ui.menu.Button(this.tr("Sharing"));
      permissionsButton.addListener("execute", () => {
        this.__openPermissions(studyData);
      }, this);
      return permissionsButton;
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

    __openPermissions: function(studyData) {
      const permissionsView = osparc.studycard.Utils.openAccessRights(studyData);
      permissionsView.getChildControl("study-link").show();
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this._resetStudyItem(updatedData);
      }, this);
    },

    __openClassifiers: function(studyData) {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (osparc.data.model.Study.isOwner(studyData)) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(studyData);
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedStudy = e.getData();
          this._resetStudyItem(updatedStudy);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(studyData);
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
      }
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

    __getDuplicateStudyMenuButton: function(studyData) {
      const duplicateStudyButton = new qx.ui.menu.Button(this.tr("Duplicate"));
      osparc.utils.Utils.setIdToWidget(duplicateStudyButton, "duplicateStudy");
      duplicateStudyButton.addListener("execute", () => {
        this.__duplicateStudy(studyData);
      }, this);
      return duplicateStudyButton;
    },

    __getExportMenuButton: function(studyData) {
      const exportButton = new qx.ui.menu.Button(this.tr("Export"));
      exportButton.addListener("execute", () => {
        this.__exportStudy(studyData);
      }, this);
      return exportButton;
    },

    __getSaveAsTemplateMenuButton: function(studyData) {
      const saveAsTemplateButton = new qx.ui.menu.Button(this.tr("Publish as Template"));
      saveAsTemplateButton.addListener("execute", () => {
        const saveAsTemplateView = new osparc.component.study.SaveAsTemplate(studyData);
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

    __getDeleteStudyMenuButton: function(studyData) {
      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"));
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => {
        const preferencesSettings = osparc.desktop.preferences.Preferences.getInstance();
        if (preferencesSettings.getConfirmDeleteStudy()) {
          const win = this.__createConfirmWindow(false);
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__deleteStudy(studyData);
            }
          }, this);
        } else {
          this.__deleteStudy(studyData);
        }
      }, this);
      return deleteButton;
    },

    __getStudyData: function(id) {
      return this.__userStudies.find(study => study.uuid === id);
    },

    __itemClicked: function(item, isShiftPressed) {
      const studiesCont = this._studiesContainer;
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
        this._startStudy(studyData);
      }
    },

    __duplicateStudy: function(studyData) {
      const duplicateTask = new osparc.component.task.Duplicate(studyData);
      duplicateTask.start();
      const text = this.tr("Duplicate process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const isGrid = this._studiesContainer.getMode() === "grid";
      const duplicatingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      duplicatingStudyCard.buildLayout(
        this.tr("Duplicating ") + studyData["name"],
        "@FontAwesome5Solid/copy/" + isGrid ? "60" : "24"
      );
      duplicatingStudyCard.subscribeToFilterGroup("sideSearchFilter");
      this._studiesContainer.addAt(duplicatingStudyCard, 1);

      const params = {
        url: {
          "studyId": studyData["uuid"]
        },
        data: osparc.utils.Utils.getClientSessionID()
      };
      osparc.data.Resources.fetch("studies", "duplicate", params)
        .then(duplicatedStudyData => {
          this.reloadStudy(duplicatedStudyData["uuid"]);
        })
        .catch(e => {
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(e.response)) || this.tr("Something went wrong Duplicating the study");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        })
        .finally(() => {
          duplicateTask.stop();
          this._studiesContainer.remove(duplicatingStudyCard);
        });
    },

    __exportStudy: function(studyData) {
      const exportTask = new osparc.component.task.Export(studyData);
      exportTask.start();
      exportTask.setSubtitle(this.tr("Preparing files"));
      const text = this.tr("Exporting process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const url = window.location.href + "v0/projects/" + studyData["uuid"] + ":xport";
      const downloadStartedCB = () => {
        const textSuccess = this.tr("Download started");
        exportTask.setSubtitle(textSuccess);
      };
      osparc.utils.Utils.downloadLink(url, "POST", null, downloadStartedCB)
        .catch(e => {
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(e.response)) || this.tr("Something went wrong Exporting the study");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        })
        .finally(() => {
          exportTask.stop();
        });
    },

    __importStudy: function(file) {
      const importTask = new osparc.component.task.Import();
      importTask.start();
      const text = this.tr("Importing process started and added to the background tasks");
      osparc.component.message.FlashMessenger.getInstance().logAs(text, "INFO");

      const uploadingLabel = this.tr("Uploading file");
      const isGrid = this._studiesContainer.getMode() === "grid";
      const importingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      importingStudyCard.buildLayout(
        this.tr("Importing Study..."),
        "@FontAwesome5Solid/cloud-upload-alt/" + isGrid ? "60" : "24",
        uploadingLabel,
        true
      );
      importingStudyCard.subscribeToFilterGroup("sideSearchFilter");
      this._studiesContainer.addAt(importingStudyCard, 1);
      importTask.setSubtitle(uploadingLabel);

      const body = new FormData();
      body.append("fileName", file);

      const req = new XMLHttpRequest();
      req.upload.addEventListener("progress", ep => {
        // updateProgress
        if (ep.lengthComputable) {
          const percentComplete = ep.loaded / ep.total * 100;
          importingStudyCard.getChildControl("progress-bar").setValue(percentComplete);
          if (percentComplete === 100) {
            const processinglabel = this.tr("Processing study");
            importingStudyCard.getChildControl("state-label").setValue(processinglabel);
            importTask.setSubtitle(processinglabel);
            importingStudyCard.getChildControl("progress-bar").exclude();
          }
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      req.addEventListener("load", e => {
        // transferComplete
        if (req.status == 200) {
          const processinglabel = this.tr("Processing study");
          importingStudyCard.getChildControl("state-label").setValue(processinglabel);
          importTask.setSubtitle(processinglabel);
          importingStudyCard.getChildControl("progress-bar").exclude();
          const data = JSON.parse(req.responseText);
          const params = {
            url: {
              "studyId": data["data"]["uuid"]
            }
          };
          osparc.data.Resources.getOne("studies", params)
            .then(studyData => {
              this._resetStudyItem(studyData);
            })
            .catch(err => {
              console.log(err);
              const msg = this.tr("Something went wrong Fetching the study");
              osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
            })
            .finally(() => {
              importTask.stop();
              this._studiesContainer.remove(importingStudyCard);
            });
        } else if (req.status == 400) {
          importTask.stop();
          this._studiesContainer.remove(importingStudyCard);
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(req.response)) || this.tr("Something went wrong Importing the study");
          osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
        }
      });
      req.addEventListener("error", e => {
        // transferFailed
        importTask.stop();
        this._studiesContainer.remove(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
      });
      req.addEventListener("abort", e => {
        // transferAborted
        importTask.stop();
        this._studiesContainer.remove(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.component.message.FlashMessenger.logAs(msg, "ERROR");
      });
      req.open("POST", "/v0/projects:import", true);
      req.send(body);
    },

    __deleteStudy: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        // remove collaborator
        osparc.component.permissions.Study.removeCollaborator(studyData, myGid);
        const params = {
          url: {
            "studyId": studyData.uuid
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
      const confirmationWin = new osparc.ui.window.Confirmation(msg);
      const confirmButton = confirmationWin.getConfirmButton();
      osparc.utils.Utils.setIdToWidget(confirmButton, "confirmDeleteStudyBtn");
      return confirmationWin;
    }
  }
});
