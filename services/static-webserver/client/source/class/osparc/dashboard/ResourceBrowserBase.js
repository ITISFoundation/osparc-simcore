/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget (base class) that shows some resources in the Dashboard.
 *
 * It used by the following tabbed elements in the main view:
 * - Study Browser
 * - Template Browser
 * - Service Browser
 */

qx.Class.define("osparc.dashboard.ResourceBrowserBase", {
  type: "abstract",
  extend: osparc.ui.basic.LoadingPageHandler,

  construct: function() {
    this.base(arguments);

    this._resourcesInitialized = false;

    this._showLoadingPage(this.tr("Starting") + " " + osparc.store.StaticInfo.getInstance().getDisplayName());

    const padding = osparc.dashboard.Dashboard.PADDING;
    const leftColumnWidth = this.self().SIDE_SPACER_WIDTH;
    const emptyColumnMinWidth = 50;
    const spacing = 20;
    const mainLayoutsScroll = 8;

    const mainLayoutWithSideSpacers = new qx.ui.container.Composite(new qx.ui.layout.HBox(spacing))
    this._addToMainLayout(mainLayoutWithSideSpacers);

    this._leftFilters = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
      width: leftColumnWidth
    });
    mainLayoutWithSideSpacers.add(this._leftFilters);

    this.__centerLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(15));
    mainLayoutWithSideSpacers.add(this.__centerLayout);

    const rightColum = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    mainLayoutWithSideSpacers.add(rightColum, {
      flex: 1
    });

    const itemWidth = osparc.dashboard.GridButtonBase.ITEM_WIDTH + osparc.dashboard.GridButtonBase.SPACING;
    this.__centerLayout.setMinWidth(this.self().MIN_GRID_CARDS_PER_ROW * itemWidth + mainLayoutsScroll);
    const fitResourceCards = () => {
      const w = document.documentElement.clientWidth;
      const nStudies = Math.floor((w - 2*padding - 2*spacing - leftColumnWidth - emptyColumnMinWidth) / itemWidth);
      const newWidth = nStudies * itemWidth + 8;
      if (newWidth > this.__centerLayout.getMinWidth()) {
        this.__centerLayout.setWidth(newWidth);
      } else {
        this.__centerLayout.setWidth(this.__centerLayout.getMinWidth());
      }

      const compactVersion = w < this.__centerLayout.getMinWidth() + leftColumnWidth + emptyColumnMinWidth;
      rightColum.setVisibility(compactVersion ? "excluded" : "visible");
    };
    fitResourceCards();
    window.addEventListener("resize", () => fitResourceCards());

    this.addListener("appear", () => this._moreResourcesRequired());
  },

  properties: {
    multiSelection: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelection",
      apply: "_applyMultiSelection"
    },
  },

  events: {
    "changeTab": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data",
  },

  statics: {
    PAGINATED_STUDIES: 5,
    MIN_GRID_CARDS_PER_ROW: 3,
    SIDE_SPACER_WIDTH: 200,

    checkLoggedIn: function() {
      const isLogged = osparc.auth.Manager.getInstance().isLoggedIn();
      if (!isLogged) {
        const msg = qx.locale.Manager.tr("You need to be logged in to create a study");
        osparc.FlashMessenger.logAs(msg);
      }
      return isLogged;
    },

    startStudyById: function(studyId, openCB, cancelCB, isStudyCreation = false) {
      if (!osparc.dashboard.ResourceBrowserBase.checkLoggedIn()) {
        return;
      }

      const openStudy = () => {
        if (openCB) {
          openCB();
        }
        osparc.desktop.MainPageHandler.getInstance().startStudy(studyId);
      };

      const walletsEnabled = osparc.desktop.credits.Utils.areWalletsEnabled();
      if (walletsEnabled) {
        const params = {
          url: {
            studyId
          }
        };
        osparc.data.Resources.fetch("studies", "getWallet", params)
          .then(wallet => {
            if (
              isStudyCreation ||
              wallet === null ||
              osparc.desktop.credits.Utils.getWallet(wallet["walletId"]) === null
            ) {
              // pop up study options if the study was just created or if it has no wallet assigned or user has no access to it
              const resourceSelector = new osparc.study.StudyOptions(studyId);
              if (isStudyCreation) {
                resourceSelector.getChildControl("open-button").setLabel(qx.locale.Manager.tr("New"));
              }
              const win = osparc.study.StudyOptions.popUpInWindow(resourceSelector);
              win.moveItUp();
              resourceSelector.addListener("startStudy", () => {
                win.close();
                openStudy();
              });
              win.addListener("cancel", () => {
                if (cancelCB) {
                  cancelCB();
                }
              });
              resourceSelector.addListener("cancel", () => {
                win.close();
                if (cancelCB) {
                  cancelCB();
                }
              });
              // listen to "tap" instead of "execute": the "execute" is not propagated
              win.getChildControl("close-button").addListener("tap", () => {
                if (cancelCB) {
                  cancelCB();
                }
              });
            } else {
              openStudy();
            }
          })
          .catch(err => osparc.FlashMessenger.logError(err));
      } else {
        openStudy();
      }
    },

    isCardNewItem: function(card) {
      return (card instanceof osparc.dashboard.GridButtonNew || card instanceof osparc.dashboard.ListButtonNew);
    },

    isCardButtonItem: function(card) {
      return (card instanceof osparc.dashboard.GridButtonItem || card instanceof osparc.dashboard.ListButtonItem);
    },

    isCardTaskPlaceholder: function(card) {
      return (card instanceof osparc.dashboard.GridButtonTaskPlaceholder || card instanceof osparc.dashboard.ListButtonTaskPlaceholder);
    },

    createToolbarRadioButton: function(label, icon, toolTipText, pos) {
      const rButton = new qx.ui.toolbar.RadioButton().set({
        label,
        icon,
        toolTipText,
        padding: 5,
        paddingLeft: 8,
        paddingRight: 8,
        margin: 0
      });
      rButton.getContentElement().setStyles({
        "border-radius": "0px"
      });
      if (pos === "left") {
        osparc.utils.Utils.addBorderLeftRadius(rButton);
      } else if (pos === "right") {
        osparc.utils.Utils.addBorderRightRadius(rButton);
      }
      return rButton;
    }
  },

  members: {
    _leftFilters: null,
    _resourceFilter: null,
    __centerLayout: null,
    _resourceType: null,
    _resourcesList: null,
    _resourcesInitialized: null,
    _toolbar: null,
    _searchBarFilter: null,
    __viewModeLayout: null,
    _resourcesContainer: null,
    _loadingResourcesBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "resources-layout": {
          const scroll = new qx.ui.container.Scroll();
          scroll.getChildControl("pane").addListener("scrollY", () => this._moreResourcesRequired(), this);
          control = this._createLayout();
          scroll.add(control);
          this._addToLayout(scroll, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _addToLayout: function(widget, props = {}) {
      this.__centerLayout.add(widget, props)
    },

    initResources: function() {
      throw new Error("Abstract method called!");
    },

    reloadMoreResources: function() {
      throw new Error("Abstract method called!");
    },

    _createLayout: function() {
      throw new Error("Abstract method called!");
    },

    _createSearchBar: function() {
      const searchBarFilter = this._searchBarFilter = new osparc.dashboard.SearchBarFilter(this._resourceType).set({
        marginRight: 22
      });
      const textField = searchBarFilter.getChildControl("text-field");
      osparc.utils.Utils.setIdToWidget(textField, "searchBarFilter-textField-"+this._resourceType);

      this._addToLayout(searchBarFilter);
    },

    _createResourcesLayout: function(flatListId) {
      const toolbar = this._toolbar = new qx.ui.toolbar.ToolBar().set({
        backgroundColor: "transparent",
        spacing: 10,
        paddingRight: 8,
        alignY: "middle"
      });
      this._addToLayout(toolbar);

      this.__viewModeLayout = new qx.ui.toolbar.Part();

      const resourcesContainer = this._resourcesContainer = new osparc.dashboard.ResourceContainerManager(this._resourceType);
      if (flatListId) {
        const list = this._resourcesContainer.getFlatList();
        if (list) {
          osparc.utils.Utils.setIdToWidget(list, flatListId);
        }
      }
      if (this._resourceType === "study") {
        const viewMode = osparc.utils.Utils.localCache.getLocalStorageItem("studiesViewMode");
        if (viewMode) {
          this._resourcesContainer.setMode(viewMode);
        }
      }
      resourcesContainer.addListener("updateStudy", e => this._updateStudyData(e.getData()));
      resourcesContainer.addListener("updateTemplate", e => this._updateTemplateData(e.getData()));
      resourcesContainer.addListener("updateTutorial", e => this._updateTutorialData(e.getData()));
      resourcesContainer.addListener("updateService", e => this._updateServiceData(e.getData()));
      resourcesContainer.addListener("updateHypertool", e => this._updateHypertoolData(e.getData()));
      resourcesContainer.addListener("publishTemplate", e => this.fireDataEvent("publishTemplate", e.getData()));
      resourcesContainer.addListener("tagClicked", e => this._searchBarFilter.addTagActiveFilter(e.getData()));
      resourcesContainer.addListener("emptyStudyClicked", e => this._deleteResourceRequested(e.getData()));
      resourcesContainer.addListener("folderUpdated", e => this._folderUpdated(e.getData()));
      resourcesContainer.addListener("moveFolderToRequested", e => this._moveFolderToRequested(e.getData()));
      resourcesContainer.addListener("trashFolderRequested", e => this._trashFolderRequested(e.getData()));
      resourcesContainer.addListener("untrashFolderRequested", e => this._untrashFolderRequested(e.getData()));
      resourcesContainer.addListener("deleteFolderRequested", e => this._deleteFolderRequested(e.getData()));
      resourcesContainer.addListener("studyToFolderRequested", e => this._studyToFolderRequested(e.getData()));
      resourcesContainer.addListener("folderToFolderRequested", e => this._folderToFolderRequested(e.getData()));
      resourcesContainer.addListener("folderSelected", e => {
        const folderId = e.getData();
        this._folderSelected(folderId);
      }, this);
      resourcesContainer.addListener("workspaceSelected", e => {
        const workspaceId = e.getData();
        this._workspaceSelected(workspaceId);
      }, this);
      resourcesContainer.addListener("changeContext", e => {
        const {
          context,
          workspaceId,
          folderId,
        } = e.getData();
        this._changeContext(context, workspaceId, folderId);
      }, this);
      resourcesContainer.addListener("workspaceUpdated", e => this._workspaceUpdated(e.getData()));
      resourcesContainer.addListener("trashWorkspaceRequested", e => this._trashWorkspaceRequested(e.getData()));
      resourcesContainer.addListener("untrashWorkspaceRequested", e => this._untrashWorkspaceRequested(e.getData()));
      resourcesContainer.addListener("deleteWorkspaceRequested", e => this._deleteWorkspaceRequested(e.getData()));

      this._addToLayout(resourcesContainer);
    },

    _groupByChanged: function(groupBy) {
      this._resourcesContainer.setGroupBy(groupBy);
      this._reloadCards();
    },

    __viewModeChanged: function(viewMode) {
      this._resourcesContainer.setMode(viewMode);
      this._reloadCards();

      if (this._resourceType === "study") {
        osparc.utils.Utils.localCache.setLocalStorageItem("studiesViewMode", viewMode);
      }
    },

    _addGroupByButton: function() {
      const groupByMenu = new qx.ui.menu.Menu().set({
        font: "text-14"
      });
      const groupByButton = new qx.ui.form.MenuButton(this.tr("Group"), "@FontAwesome5Solid/chevron-down/10", groupByMenu);
      groupByButton.set({
        appearance: "form-button-outlined",
        marginRight: 14
      });
      osparc.utils.Utils.setIdToWidget(groupByButton, "groupByButton");

      const groupOptions = new qx.ui.form.RadioGroup();

      const dontGroup = new qx.ui.menu.RadioButton(this.tr("None"));
      osparc.utils.Utils.setIdToWidget(dontGroup, "groupByNone");
      dontGroup.addListener("execute", () => this._groupByChanged(null));

      groupByMenu.add(dontGroup);
      groupOptions.add(dontGroup);

      if (this._resourceType === "template") {
        const groupByTag = new qx.ui.menu.RadioButton(this.tr("Tags"));
        groupByTag.addListener("execute", () => this._groupByChanged("tags"));
        groupByMenu.add(groupByTag);
        groupOptions.add(groupByTag);
        if (
          osparc.product.Utils.isProduct("s4l") ||
          osparc.product.Utils.isProduct("s4lacad") ||
          osparc.product.Utils.isProduct("s4llite")
        ) {
          groupByTag.execute();
        }
      } else if (this._resourceType === "service" && osparc.product.Utils.groupServices()) {
        const groupByFeatured = new qx.ui.menu.RadioButton(this.tr("Featured"));
        groupByFeatured.addListener("execute", () => this._groupByChanged("groupedServices"));
        groupByMenu.add(groupByFeatured);
        groupOptions.add(groupByFeatured);
        groupByFeatured.execute();
        groupByButton.exclude(); // don't let users change the grouping
      }

      const groupByShared = new qx.ui.menu.RadioButton(this.tr("Shared with"));
      groupByShared.addListener("execute", () => this._groupByChanged("shared"));
      groupByMenu.add(groupByShared);
      groupOptions.add(groupByShared);

      this._toolbar.add(groupByButton);
    },

    _addViewModeButton: function() {
      const gridBtn = this.self().createToolbarRadioButton(null, "@FontAwesome5Solid/th/14", this.tr("Grid view"), "left");
      gridBtn.addListener("execute", () => this.__viewModeChanged("grid"));

      const listBtn = this.self().createToolbarRadioButton(null, "@FontAwesome5Solid/bars/14", this.tr("List view"), "right");
      listBtn.addListener("execute", () => this.__viewModeChanged("list"));

      const viewModeLayout = this.__viewModeLayout;
      const radioGroup = new qx.ui.form.RadioGroup();
      [
        gridBtn,
        listBtn
      ].forEach(btn => {
        viewModeLayout.add(btn);
        radioGroup.add(btn);
      });

      if (this._resourceType === "study") {
        const viewMode = osparc.utils.Utils.localCache.getLocalStorageItem("studiesViewMode");
        if (viewMode) {
          if (viewMode === "list") {
            radioGroup.setSelection([listBtn]);
          }
        }
      }

      this._toolbar.add(viewModeLayout);
    },

    _addResourceFilter: function() {
      const resourceFilter = this._resourceFilter = new osparc.dashboard.ResourceBrowserFilter(this._resourceType).set({
        marginTop: 20,
        maxWidth: this.self().SIDE_SPACER_WIDTH,
        width: this.self().SIDE_SPACER_WIDTH
      });

      resourceFilter.addListener("changeTab", e => {
        const contextTab = e.getData();
        this.fireDataEvent("changeTab", contextTab);
      }, this);

      resourceFilter.addListener("changeSharedWith", e => {
        const sharedWith = e.getData();
        this._searchBarFilter.setSharedWithActiveFilter(sharedWith.id, sharedWith.label);
      }, this);

      resourceFilter.addListener("changeSelectedTags", e => {
        const selectedTagIds = e.getData();
        this._searchBarFilter.setTagsActiveFilter(selectedTagIds);
      }, this);

      resourceFilter.addListener("changeAppType", e => {
        const appType = e.getData();
        this._searchBarFilter.setAppTypeActiveFilter(appType.appType, appType.label);
      }, this);

      this._searchBarFilter.addListener("filterChanged", e => {
        const filterData = e.getData();
        resourceFilter.filterChanged(filterData);
      });

      this._leftFilters.add(resourceFilter, {
        flex: 1
      });
    },

    /**
     * Function that resets the selected item
     */
    resetSelection: function() {
      if (this._resourcesContainer) {
        this._resourcesContainer.resetSelection();
      }
    },

    _checkLoggedIn: function() {
      let isLogged = osparc.auth.Manager.getInstance().isLoggedIn();
      if (!isLogged) {
        const msg = this.tr("You need to be logged in to create a study");
        osparc.FlashMessenger.logAs(msg);
      }
      return isLogged;
    },

    _removeResourceCards: function() {
      const cards = this._resourcesContainer.getCards();
      for (let i=cards.length-1; i>=0; i--) {
        const card = cards[i];
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)) {
          this._resourcesContainer.removeNonResourceCard(card);
        }
      }
    },

    _moreResourcesRequired: function() {
      if (this._resourcesContainer && this._resourcesContainer.areMoreResourcesRequired(this._loadingResourcesBtn)) {
        this.reloadMoreResources();
      }
    },

    taskToTemplateReceived: function(task, studyName, templateType) {
      const toTemplateTaskUI = new osparc.task.ToTemplate(studyName);
      toTemplateTaskUI.setTask(task);

      osparc.task.TasksContainer.getInstance().addTaskUI(toTemplateTaskUI);

      const cardTitle = this.tr("Publishing ") + studyName;
      const toTemplateCard = this._addTaskCard(task, cardTitle, osparc.task.ToTemplate.ICON);
      if (toTemplateCard) {
        this.__attachToTemplateEventHandler(task, toTemplateCard, templateType);
      }
    },

    __attachToTemplateEventHandler: function(task, toTemplateCard, templateType) {
      const finished = () => {
        this._resourcesContainer.removeNonResourceCard(toTemplateCard);
      };

      task.addListener("updateReceived", e => {
        const updateData = e.getData();
        if ("task_progress" in updateData && toTemplateCard) {
          const taskProgress = updateData["task_progress"];
          toTemplateCard.getChildControl("progress-bar").set({
            value: osparc.data.PollTask.extractProgress(updateData) * 100
          });
          toTemplateCard.getChildControl("state-label").set({
            value: taskProgress["message"]
          });
        }
      }, this);
      task.addListener("resultReceived", e => {
        finished();
        this.reloadResources();
        const userFriendlyType = templateType.charAt(0).toUpperCase() + templateType.slice(1).toLowerCase();
        const msg = userFriendlyType + this.tr(" created");
        osparc.FlashMessenger.logAs(msg, "INFO");
      });
      task.addListener("taskAborted", () => {
        finished();
        const msg = this.tr("Study to Template cancelled");
        osparc.FlashMessenger.logAs(msg, "WARNING");
      });
      task.addListener("pollingError", e => {
        finished();
        const err = e.getData();
        osparc.FlashMessenger.logError(err);
      });
    },

    _addTaskCard: function(task, cardTitle, cardIcon) {
      if (!this._resourcesContainer) {
        return null;
      }

      if (task) {
        const taskPlaceholders = this._resourcesContainer.getCards().filter(card => osparc.dashboard.ResourceBrowserBase.isCardTaskPlaceholder(card));
        if (taskPlaceholders.find(taskPlaceholder => taskPlaceholder.getTask() === task)) {
          return null;
        }
      }

      const isGrid = this._resourcesContainer.getMode() === "grid";
      const taskCard = isGrid ? new osparc.dashboard.GridButtonTaskPlaceholder() : new osparc.dashboard.ListButtonTaskPlaceholder();
      taskCard.setTask(task);
      taskCard.buildLayout(
        cardTitle,
        cardIcon + (isGrid ? "/60" : "/24"),
        null,
        true
      );
      taskCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addNonResourceCard(taskCard);
      return taskCard;
    },

    _removeTaskCard: function(task) {
      if (!this._resourcesContainer) {
        return;
      }

      if (task) {
        const taskPlaceholders = this._resourcesContainer.getCards().filter(card => osparc.dashboard.ResourceBrowserBase.isCardTaskPlaceholder(card));
        const taskCard = taskPlaceholders.find(taskPlaceholder => taskPlaceholder.getTask() === task);
        if (taskCard) {
          this._resourcesContainer.removeNonResourceCard(taskCard);
        }
      }
    },

    _populateCardMenu: function(card) {
      throw new Error("Abstract method called!");
    },

    _updateStudyData: function(studyData) {
      throw new Error("Abstract method called!");
    },

    _populateTemplateCardMenu: function(card) {
      const menu = card.getMenu();
      const templateData = card.getResourceData();

      const editButton = this.__getEditTemplateMenuButton(templateData);
      if (editButton) {
        menu.add(editButton);
        menu.addSeparator();
      }

      const openButton = this._getOpenMenuButton(templateData);
      if (openButton) {
        menu.add(openButton);
      }

      const shareButton = this._getShareMenuButton(card);
      if (shareButton) {
        menu.add(shareButton);
      }

      const tagsButton = this._getTagsMenuButton(card);
      if (tagsButton) {
        menu.add(tagsButton);
      }

      const deleteButton = this.__getDeleteTemplateMenuButton(templateData);
      if (deleteButton && editButton) {
        menu.addSeparator();
        menu.add(deleteButton);
      }
    },

    __getEditTemplateMenuButton: function(templateData) {
      const isCurrentUserOwner = osparc.data.model.Study.canIWrite(templateData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const editButton = new qx.ui.menu.Button(this.tr("Edit"));
      editButton.addListener("execute", () => {
        const isStudyCreation = false;
        this._startStudyById(templateData["uuid"], null, null, isStudyCreation);
      }, this);
      return editButton;
    },

    __getDeleteTemplateMenuButton: function(templateData) {
      const isCurrentUserOwner = osparc.data.model.Study.canIDelete(templateData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/12");
      deleteButton.set({
        appearance: "menu-button"
      });
      deleteButton.addListener("execute", () => this._deleteTemplateRequested(templateData), this);
      return deleteButton;
    },

    _deleteTemplateRequested: function(templateData) {
      const rUSure = this.tr("Are you sure you want to delete ");
      const msg = rUSure + "<b>" + templateData.name + "</b>?";
      const win = new osparc.ui.window.Confirmation(msg).set({
        caption: this.tr("Delete"),
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      win.center();
      win.open();
      win.addListener("close", () => {
        if (win.getConfirmed()) {
          this.__doDeleteTemplate(templateData);
        }
      }, this);
    },

    __doDeleteTemplate: function(templateData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(templateData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        const arCopy = osparc.utils.Utils.deepCloneObject(templateData["accessRights"]);
        // remove collaborator
        delete arCopy[myGid];
        operationPromise = osparc.store.Study.patchStudyData(templateData, "accessRights", arCopy);
      } else {
        // delete study
        operationPromise = osparc.store.Store.getInstance().deleteStudy(templateData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromTemplateList(templateData.uuid))
        .catch(err => osparc.FlashMessenger.logError(err));
    },

    __removeFromTemplateList: function(templateId) {
      const idx = this._resourcesList.findIndex(study => study["uuid"] === templateId);
      if (idx > -1) {
        this._resourcesList.splice(idx, 1);
      }
      this._resourcesContainer.removeCard(templateId);
    },

    _updateTemplateData: function(templateData) {
      const templatesList = this._resourcesList;
      const index = templatesList.findIndex(template => template["uuid"] === templateData["uuid"]);
      if (index !== -1) {
        templatesList[index] = templateData;
        this._reloadCards();
      }
    },

    updateTutorialData: function(tutorialData) {
      throw new Error("Abstract method called!");
    },

    _updateServiceData: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    _updateHypertoolData: function(serviceData) {
      throw new Error("Abstract method called!");
    },

    _startStudyById: function(studyId, openCB, cancelCB, isStudyCreation = false) {
      if (isStudyCreation) {
        this.fireDataEvent("changeTab", "studiesTab");
      }
      this.self().startStudyById(studyId, openCB, cancelCB, isStudyCreation);
    },

    _createStudyFromTemplate: function(templateData) {
      if (!this._checkLoggedIn()) {
        return;
      }

      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      this._showLoadingPage(this.tr("Creating ") + (templateData.name || studyAlias));

      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const studyOptions = new osparc.study.StudyOptions();
        // they will be patched once the study is created
        studyOptions.setPatchStudy(false);
        studyOptions.setStudyData(templateData);
        studyOptions.getChildControl("open-button").setLabel(this.tr("New"));
        const win = osparc.study.StudyOptions.popUpInWindow(studyOptions);
        win.moveItUp();
        const cancelStudyOptions = () => {
          this._hideLoadingPage();
          win.close();
        }
        win.addListener("cancel", () => cancelStudyOptions());
        studyOptions.addListener("cancel", () => cancelStudyOptions());
        studyOptions.addListener("startStudy", () => {
          const newName = studyOptions.getChildControl("title-field").getValue();
          const walletSelection = studyOptions.getChildControl("wallet-selector").getSelection();
          const nodesPricingUnits = studyOptions.getChildControl("study-pricing-units").getNodePricingUnits();
          win.close();

          this._showLoadingPage(this.tr("Creating ") + (newName || studyAlias));
          osparc.study.Utils.createStudyFromTemplate(templateData, this._loadingPage)
            .then(newStudyData => {
              const studyId = newStudyData["uuid"];
              const openCB = () => {
                this._hideLoadingPage();
              };
              const cancelCB = () => {
                this._hideLoadingPage();
                const params = {
                  url: {
                    studyId
                  }
                };
                osparc.data.Resources.fetch("studies", "delete", params);
              };

              const promises = [];
              // patch the name
              if (newStudyData["name"] !== newName) {
                promises.push(osparc.study.StudyOptions.updateName(newStudyData, newName));
              }
              // patch the wallet
              if (walletSelection.length && walletSelection[0]["walletId"]) {
                const walletId = walletSelection[0]["walletId"];
                promises.push(osparc.study.StudyOptions.updateWallet(newStudyData["uuid"], walletId));
              }
              // patch the pricing units
              // the nodeIds are coming from the original template, they need to be mapped to the newStudy
              const workbench = newStudyData["workbench"];
              const nodesIdsListed = [];
              Object.keys(workbench).forEach(nodeId => {
                const nodeData = workbench[nodeId];
                if (osparc.study.StudyPricingUnits.includeInList(nodeData)) {
                  nodesIdsListed.push(nodeId);
                }
              });
              nodesPricingUnits.forEach((nodePricingUnits, idx) => {
                const selectedPricingUnitId = nodePricingUnits.getPricingUnits().getSelectedUnitId();
                if (selectedPricingUnitId) {
                  const nodeId = nodesIdsListed[idx];
                  const pricingPlanId = nodePricingUnits.getPricingPlanId();
                  promises.push(osparc.study.NodePricingUnits.patchPricingUnitSelection(studyId, nodeId, pricingPlanId, selectedPricingUnitId));
                }
              });

              Promise.all(promises)
                .then(() => {
                  win.close();
                  const showStudyOptions = false;
                  this._startStudyById(studyId, openCB, cancelCB, showStudyOptions);
                });
            })
            .catch(err => {
              this._hideLoadingPage();
              osparc.FlashMessenger.logError(err);
            });
        });
      } else {
        osparc.study.Utils.createStudyFromTemplate(templateData, this._loadingPage)
          .then(newStudyData => {
            const studyId = newStudyData["uuid"];
            const openCB = () => this._hideLoadingPage();
            const cancelCB = () => {
              this._hideLoadingPage();
              const params = {
                url: {
                  studyId
                }
              };
              osparc.data.Resources.fetch("studies", "delete", params);
            };
            const isStudyCreation = true;
            this._startStudyById(studyId, openCB, cancelCB, isStudyCreation);
          })
          .catch(err => {
            this._hideLoadingPage();
            osparc.FlashMessenger.logError(err);
          });
      }
    },

    _createStudyFromService: function(key, version) {
      if (!this._checkLoggedIn()) {
        return;
      }

      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      this._showLoadingPage(this.tr("Creating ") + studyAlias);

      osparc.study.Utils.createStudyFromService(key, version)
        .then(studyId => {
          const openCB = () => this._hideLoadingPage();
          const cancelCB = () => {
            this._hideLoadingPage();
            const params = {
              url: {
                studyId
              }
            };
            osparc.data.Resources.fetch("studies", "delete", params);
          };
          const isStudyCreation = true;
          this._startStudyById(studyId, openCB, cancelCB, isStudyCreation);
        })
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.logError(err);
        });
    },

    _applyMultiSelection: function(value) {
      return;
    },

    _deleteResourceRequested: function(resourceId) {
      throw new Error("Abstract method called!");
    },

    _changeContext: function(context, workspaceId, folderId) {
      throw new Error("Abstract method called!");
    },

    _folderSelected: function(folderId) {
      throw new Error("Abstract method called!");
    },

    _folderUpdated: function(folderId) {
      throw new Error("Abstract method called!");
    },

    _moveFolderToRequested: function(folderId) {
      throw new Error("Abstract method called!");
    },

    _trashFolderRequested: function(folderId) {
      throw new Error("Abstract method called!");
    },

    _untrashFolderRequested: function(folder) {
      throw new Error("Abstract method called!");
    },

    _deleteFolderRequested: function(folderId) {
      throw new Error("Abstract method called!");
    },

    _studyToFolderRequested: function(studyId) {
      throw new Error("Abstract method called!");
    },

    _folderToFolderRequested: function(folderId) {
      throw new Error("Abstract method called!");
    },

    _workspaceSelected: function(workspaceId) {
      throw new Error("Abstract method called!");
    },

    _workspaceUpdated: function(workspaceId) {
      throw new Error("Abstract method called!");
    },

    _deleteWorkspaceRequested: function(workspaceId) {
      throw new Error("Abstract method called!");
    },

    _getOpenMenuButton: function(resourceData) {
      const studyAlias = osparc.product.Utils.getStudyAlias({firstUpperCase: true});
      const openText = (resourceData["resourceType"] === "study") ? this.tr("Open") : this.tr("New") + " " + studyAlias;
      const openButton = new qx.ui.menu.Button(openText);
      openButton["openResourceButton"] = true;
      openButton.addListener("execute", () => {
        switch (resourceData["resourceType"]) {
          case "study": {
            const isStudyCreation = false;
            this._startStudyById(resourceData["uuid"], null, null, isStudyCreation);
            break;
          }
          case "template":
          case "tutorial":
          case "hypertool":
            this._createStudyFromTemplate(resourceData);
            break;
          case "service":
            this._createStudyFromService(resourceData["key"], resourceData["version"]);
            break;
        }
      }, this);
      return openButton;
    },

    _openResourceDetails: function(resourceData) {
      const resourceDetails = new osparc.dashboard.ResourceDetails(resourceData);
      const win = osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
      resourceDetails.addListener("updateStudy", e => this._updateStudyData(e.getData()));
      resourceDetails.addListener("updateTemplate", e => this._updateTemplateData(e.getData()));
      resourceDetails.addListener("updateTutorial", e => this._updateTutorialData(e.getData()));
      resourceDetails.addListener("updateService", e => this._updateServiceData(e.getData()));
      resourceDetails.addListener("updateHypertool", e => this._updateHypertoolData(e.getData()));
      resourceDetails.addListener("publishTemplate", e => {
        win.close();
        this.fireDataEvent("publishTemplate", e.getData());
      });
      resourceDetails.addListener("openStudy", e => {
        const openCB = () => win.close();
        const studyId = e.getData()["uuid"];
        const isStudyCreation = false;
        this._startStudyById(studyId, openCB, null, isStudyCreation);
      });
      [
        "openTemplate",
        "openTutorial",
        "openHypertool",
      ].forEach(eventName => {
        resourceDetails.addListener(eventName, e => {
          win.close();
          const templateData = e.getData();
          this._createStudyFromTemplate(templateData);
        });
      });
      resourceDetails.addListener("openService", e => {
        win.close();
        const openServiceData = e.getData();
        this._createStudyFromService(openServiceData["key"], openServiceData["version"]);
      });
      return resourceDetails;
    },

    _getShareMenuButton: function(card) {
      const resourceData = card.getResourceData();
      const isCurrentUserOwner = osparc.data.model.Study.canIWrite(resourceData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const shareButton = new qx.ui.menu.Button(this.tr("Share..."), "@FontAwesome5Solid/share-alt/12");
      shareButton.addListener("tap", () => card.openAccessRights(), this);
      return shareButton;
    },

    _getTagsMenuButton: function(card) {
      const resourceData = card.getResourceData();
      const isCurrentUserOwner = osparc.data.model.Study.canIWrite(resourceData["accessRights"]);
      if (!isCurrentUserOwner) {
        return null;
      }

      const tagsButton = new qx.ui.menu.Button(this.tr("Tags..."), "@FontAwesome5Solid/tags/12");
      tagsButton.addListener("tap", () => card.openTags(), this);
      return tagsButton;
    }
  }
});
