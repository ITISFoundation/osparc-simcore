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
 * @asset(osparc/new_studies.json")
 */

/**
 * Widget that shows lists user's studies.
 *
 * It is the entry point to start editing or creating a new study.
 *
 * Also takes care of retrieving the list of services and pushing the changes in the metadata.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let studyBrowser = new osparc.dashboard.StudyBrowser();
 *   this.getRoot().add(studyBrowser);
 * </pre>
 */

qx.Class.define("osparc.dashboard.StudyBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  construct: function() {
    this._resourceType = "study";
    this.base(arguments);
  },

  events: {
    "publishTemplate": "qx.event.type.Data"
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentWorkspaceId"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId"
    },

    multiSelection: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeMultiSelection",
      apply: "__applyMultiSelection"
    },

    // Ordering by Possibilities:
    // field: type | uuid | name | description | prj_owner | creation_date | last_change_date
    // direction: asc | desc
    orderBy: {
      check: "Object",
      init: {
        field: "last_change_date",
        direction: "desc"
      }
    }
  },

  statics: {
    sortFoldersList: function(foldersList, propKey) {
      const sortByProperty = prop => {
        return function(a, b) {
          const upKey = qx.lang.String.firstUp(prop);
          const getter = "get" + upKey;
          if (getter in a && getter in b) {
            return b[getter]() - a[getter]();
          }
          return 0;
        };
      };
      foldersList.sort(sortByProperty(propKey || "lastModified"));
    }
  },

  members: {
    __dontShowTutorial: null,
    __workspacesList: null,
    __foldersList: null,

    // overridden
    initResources: function() {
      this._resourcesList = [];
      this.__getActiveStudy()
        .then(() => {
          this.getChildControl("resources-layout");
          this.__attachEventHandlers();
          // set by the url or active study
          const loadStudyId = osparc.store.Store.getInstance().getCurrentStudyId();
          if (loadStudyId) {
            const cancelCB = () => this.reloadResources();
            const isStudyCreation = false;
            this._startStudyById(loadStudyId, null, cancelCB, isStudyCreation);
          } else {
            this.__reloadFolders();
            this.reloadResources();
          }
          // "Starting..." page
          this._hideLoadingPage();
        })
        .catch(console.error);
    },

    __getActiveStudy: function() {
      const params = {
        url: {
          tabId: osparc.utils.Utils.getClientSessionID()
        }
      };
      return osparc.data.Resources.fetch("studies", "getActive", params)
        .then(studyData => {
          if (studyData) {
            osparc.store.Store.getInstance().setCurrentStudyId(studyData["uuid"]);
          }
        })
        .catch(err => console.error(err));
    },

    reloadResources: function() {
      if (
        osparc.data.Permissions.getInstance().canDo("studies.user.read") &&
        osparc.auth.Manager.getInstance().isLoggedIn()
      ) {
        this.__reloadStudies();
      } else {
        this.__resetStudiesList();
      }
    },

    __reloadFoldersAndStudies: function() {
      this.__reloadFolders();
      this.__reloadStudies();
    },

    __reloadFilteredResources: function() {
      this.__reloadFilteredStudies();
    },

    __reloadWorkspaces: function() {
      this.__setWorkspacesToList([]);
      osparc.store.Workspaces.getInstance().fetchWorkspaces()
        .then(workspaces => {
          this.__setWorkspacesToList(workspaces);
        });
    },

    __reloadFolders: function() {
      if (osparc.utils.DisabledPlugins.isFoldersEnabled()) {
        const folderId = this.getCurrentFolderId();
        const workspaceId = this.getCurrentWorkspaceId();
        if (workspaceId === -1) {
          return;
        }
        this.__setFoldersToList([]);
        osparc.store.Folders.getInstance().fetchFolders(folderId, workspaceId)
          .then(folders => {
            this.__setFoldersToList(folders);
          })
          .catch(console.error);
      }
    },

    __reloadStudies: function() {
      if (this._loadingResourcesBtn.isFetching()) {
        return;
      }
      const workspaceId = this.getCurrentWorkspaceId();
      if (workspaceId === -1) {
        return;
      }

      osparc.data.Resources.get("tasks")
        .then(tasks => {
          if (tasks && tasks.length) {
            this.__tasksReceived(tasks);
          }
        });

      // Show "Contact Us" message if services.length === 0
      // Most probably is a product-stranger user (it can also be that the catalog is down)
      osparc.store.Services.getServicesLatest()
        .then(services => {
          if (Object.keys(services).length === 0) {
            const noAccessText = new qx.ui.basic.Label().set({
              selectable: true,
              rich: true,
              font: "text-18",
              paddingTop: 20
            });
            let msg = this.tr("It seems you don't have access to this product.");
            msg += "</br>";
            msg += "</br>";
            msg += this.tr("Please contact us:");
            msg += "</br>";
            const supportEmail = osparc.store.VendorInfo.getInstance().getSupportEmail();
            noAccessText.setValue(msg + supportEmail);
            this._addToLayout(noAccessText);
          }
        });

      this._loadingResourcesBtn.setFetching(true);
      this._loadingResourcesBtn.setVisibility("visible");
      this.__getNextStudiesRequest()
        .then(resp => {
          if (
            resp["params"]["url"].workspaceId !== this.getCurrentWorkspaceId() ||
            resp["params"]["url"].folderId !== this.getCurrentFolderId()
          ) {
            // Context might have been changed while waiting for the response.
            // The new call is on the ways and this can be ignored.
            return;
          }

          const studies = resp["data"];
          this._resourcesContainer.getFlatList().nextRequest = resp["_links"]["next"];
          this.__addStudiesToList(studies);

          // Show Quick Start if there are no studies in the root folder of the personal workspace
          const quickStartInfo = osparc.product.quickStart.Utils.getQuickStart();
          if (quickStartInfo) {
            const dontShow = osparc.utils.Utils.localCache.getLocalStorageItem(quickStartInfo.localStorageStr);
            if (dontShow === "true" || this.__dontShowTutorial) {
              return;
            }
            const nStudies = "_meta" in resp ? resp["_meta"]["total"] : 0;
            if (
              nStudies === 0 &&
              this.getCurrentWorkspaceId() === null &&
              this.getCurrentFolderId() === null
            ) {
              const quickStartWindow = quickStartInfo.tutorial();
              quickStartWindow.center();
              quickStartWindow.open();
              quickStartWindow.addListener("close", () => {
                this.__dontShowTutorial = true;
              }, this);
            }
          }
        })
        .catch(err => console.error(err))
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __reloadFilteredStudies: function(text) {
      if (this._loadingResourcesBtn.isFetching()) {
        return;
      }
      this.__resetStudiesList();
      this._loadingResourcesBtn.setFetching(true);
      this._loadingResourcesBtn.setVisibility("visible");
      const request = this.__getTextFilteredNextRequest(text);
      request
        .then(resp => {
          const filteredStudies = resp["data"];
          this._resourcesContainer.getFlatList().nextRequest = resp["_links"]["next"];
          this.__addStudiesToList(filteredStudies);
        })
        .catch(err => console.error(err))
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __reloadSortedByStudies: function() {
      if (this._loadingResourcesBtn.isFetching()) {
        return;
      }
      this.__resetStudiesList();
      this._loadingResourcesBtn.setFetching(true);
      this._loadingResourcesBtn.setVisibility("visible");
      const request = this.__getSortedByNextRequest();
      request
        .then(resp => {
          const sortedStudies = resp["data"];
          this._resourcesContainer.getFlatList().nextRequest = resp["_links"]["next"];
          this.__addStudiesToList(sortedStudies);
        })
        .catch(err => console.error(err))
        .finally(() => {
          this._loadingResourcesBtn.setFetching(false);
          this._loadingResourcesBtn.setVisibility(this._resourcesContainer.getFlatList().nextRequest === null ? "excluded" : "visible");
          this._moreResourcesRequired();
        });
    },

    __resetStudiesList: function() {
      this._resourcesList = [];
      this._reloadCards();
    },

    __addStudiesToList: function(studiesList) {
      studiesList.forEach(study => study["resourceType"] = "study");
      studiesList.forEach(study => {
        const idx = this._resourcesList.findIndex(std => std["uuid"] === study["uuid"]);
        if (idx === -1) {
          this._resourcesList.push(study);
        }
      });
      this._reloadNewCards();

      studiesList.forEach(study => {
        const state = study["state"];
        if (state && "locked" in state && state["locked"]["value"] && state["locked"]["status"] === "CLOSING") {
          // websocket might have already notified that the state was closed.
          // But the /projects calls response got after the ws message. Ask again to make sure
          const delay = 2000;
          const studyId = study["uuid"];
          setTimeout(() => {
            const params = {
              url: {
                studyId
              }
            };
            osparc.data.Resources.getOne("studies", params)
              .then(studyData => {
                this.__studyStateReceived(study["uuid"], studyData["state"]);
              });
          }, delay);
        }
      });
    },

    __setFoldersToList: function(folders) {
      this.__foldersList = folders;
      folders.forEach(folder => folder["resourceType"] = "folder");

      const sortByValueBE = this.getOrderBy().field;
      let sortByValue = null;
      switch (sortByValueBE) {
        case "name":
          sortByValue = "name";
          break;
        case "prj_owner":
          sortByValue = "owner";
          break;
        case "creation_date":
          sortByValue = "createdAt";
          break;
        case "last_change_date":
          sortByValue = "lastModified";
          break;
      }
      this.self().sortFoldersList(this.__foldersList, sortByValue);
      this.__reloadFolderCards();
    },

    __setWorkspacesToList: function(workspaces) {
      this.__workspacesList = workspaces;
      workspaces.forEach(workspace => workspace["resourceType"] = "workspace");
      this.__reloadWorkspaceCards();
    },

    _reloadCards: function() {
      const fetching = this._loadingResourcesBtn ? this._loadingResourcesBtn.getFetching() : false;
      const visibility = this._loadingResourcesBtn ? this._loadingResourcesBtn.getVisibility() : "excluded";

      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadCards("studies");
      this.__configureStudyCards(cards);

      this.__addNewStudyButtons();

      const loadMoreBtn = this.__createLoadMoreButton();
      loadMoreBtn.set({
        fetching,
        visibility
      });
      loadMoreBtn.addListener("appear", () => this._moreResourcesRequired());
      this._resourcesContainer.addNonResourceCard(loadMoreBtn);

      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    _reloadNewCards: function() {
      this._resourcesContainer.setResourcesToList(this._resourcesList);
      const cards = this._resourcesContainer.reloadNewCards();
      this.__configureStudyCards(cards);

      osparc.filter.UIFilterController.dispatch("searchBarFilter");
    },

    // WORKSPACES
    __reloadWorkspaceCards: function() {
      this._resourcesContainer.setWorkspacesToList(this.__workspacesList);
      this._resourcesContainer.reloadWorkspaces();

      const newWorkspaceCard = new osparc.dashboard.WorkspaceButtonNew();
      newWorkspaceCard.setCardKey("new-workspace");
      newWorkspaceCard.subscribeToFilterGroup("searchBarFilter");
      [
        "createWorkspace",
        "updateWorkspace"
      ].forEach(e => {
        newWorkspaceCard.addListener(e, () => {
          this.__reloadWorkspaces();
        });
      });
      this._resourcesContainer.addNewWorkspaceCard(newWorkspaceCard);
    },

    _workspaceSelected: function(workspaceId) {
      this.setCurrentWorkspaceId(workspaceId);
      this._changeContext(this.getCurrentWorkspaceId(), null);
    },

    _workspaceUpdated: function() {
      this.__reloadWorkspaceCards();
    },

    _deleteWorkspaceRequested: function(workspaceId) {
      osparc.store.Workspaces.getInstance().deleteWorkspace(workspaceId)
        .then(() => {
          this.__reloadWorkspaces();
        })
        .catch(err => console.error(err));
    },
    // /WORKSPACES

    _changeContext: function(workspaceId, folderId) {
      if (osparc.utils.DisabledPlugins.isFoldersEnabled()) {
        this.set({
          currentWorkspaceId: workspaceId,
          currentFolderId: folderId,
        });
        this.invalidateStudies();
        this._resourcesContainer.setResourcesToList([]);

        if (workspaceId === -1) {
          this.__reloadWorkspaces();
        } else {
          this.__reloadFoldersAndStudies();
        }
      }
    },

    // FOLDERS
    __reloadFolderCards: function() {
      this._resourcesContainer.setFoldersToList(this.__foldersList);
      this._resourcesContainer.reloadFolders();

      this.__addNewFolderButton();
    },

    __addNewFolderButton: function() {
      if (this.getCurrentWorkspaceId()) {
        const currentWorkspace = osparc.store.Workspaces.getInstance().getWorkspace(this.getCurrentWorkspaceId());
        if (currentWorkspace && !currentWorkspace.getMyAccessRights()["write"]) {
          // If user can't write in workspace, do not show plus button
          return;
        }
        const newFolderCard = new osparc.dashboard.FolderButtonNew();
        newFolderCard.setCardKey("new-folder");
        newFolderCard.subscribeToFilterGroup("searchBarFilter");
        newFolderCard.addListener("createFolder", e => {
          const data = e.getData();
          this.__createFolder(data);
        }, this);
        this._resourcesContainer.addNewFolderCard(newFolderCard);
      }
    },

    __createFolder: function(data) {
      const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId())
      const parentFolderId = currentFolder ? currentFolder.getFolderId() : null;
      const currentWorkspaceId = this.getCurrentWorkspaceId();
      osparc.store.Folders.getInstance().postFolder(data.name, parentFolderId, currentWorkspaceId)
        .then(() => this.__reloadFolders())
        .catch(err => console.error(err));
    },

    _folderSelected: function(folderId) {
      this.setCurrentFolderId(folderId);
      this._changeContext(this.getCurrentWorkspaceId(), folderId);
    },

    _folderUpdated: function() {
      this.__reloadFolders();
    },

    _moveFolderToFolderRequested: function(folderId) {
      const moveFolderToFolder = new osparc.dashboard.MoveResourceToFolder(this.getCurrentFolderId(), this.getCurrentWorkspaceId());
      const title = "Move to Folder";
      const win = osparc.ui.window.Window.popUpInWindow(moveFolderToFolder, title, 350, 280);
      moveFolderToFolder.addListener("moveToFolder", e => {
        win.close();
        const folder = osparc.store.Folders.getInstance().getFolder(folderId);
        const destFolderId = e.getData();
        const updatedData = {
          name: folder.getName(),
          parentFolderId: destFolderId,
        };
        osparc.store.Folders.getInstance().putFolder(folderId, updatedData)
          .then(() => {
            folder.setParentFolderId(destFolderId);
            this.__reloadFolders()
          })
          .catch(err => console.error(err));
      });
    },

    __showMoveToWorkspaceWarningMessage: function() {
      const msg = this.tr("The permissions will be taken from the new workspace?");
      const win = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Move"),
      });
      win.open();
      return win;
    },

    _moveFolderToWorkspaceRequested: function(folderId) {
      const folderToWorkspaceRequested = false;
      if (!folderToWorkspaceRequested) {
        const msg = this.tr("Coming soon");
        osparc.FlashMessenger.getInstance().logAs(msg, "WARNING");
        return;
      }
      const moveFolderToWorkspace = new osparc.dashboard.MoveResourceToWorkspace(this.getCurrentWorkspaceId());
      const title = "Move to Workspace";
      const win = osparc.ui.window.Window.popUpInWindow(moveFolderToWorkspace, title, 350, 280);
      moveFolderToWorkspace.addListener("moveToWorkspace", e => {
        win.close();
        const destWorkspaceId = e.getData();
        const confirmationWin = this.__showMoveToWorkspaceWarningMessage();
        confirmationWin.addListener("close", () => {
          if (confirmationWin.getConfirmed()) {
            const params = {
              url: {
                folderId,
                workspaceId: destWorkspaceId,
              }
            };
            osparc.data.Resources.fetch("folders", "moveToWorkspace", params)
              .then(() => {
                const folder = osparc.store.Folders.getInstance().getFolder(folderId);
                if (folder) {
                  folder.setWorkspaceId(destWorkspaceId);
                }
                this.__reloadFolders()
              })
              .catch(err => console.error(err));
          }
        }, this);
      }, this);
    },

    _deleteFolderRequested: function(folderId) {
      osparc.store.Folders.getInstance().deleteFolder(folderId, this.getCurrentWorkspaceId())
        .then(() => this.__reloadFolders())
        .catch(err => console.error(err));
    },
    // /FOLDERS

    __configureStudyCards: function(cards) {
      cards.forEach(card => {
        card.setMultiSelectionMode(this.getMultiSelection());
        card.addListener("tap", e => {
          if (card.getBlocked() === true) {
            card.setValue(false);
          } else {
            this.__itemClicked(card, e.getNativeEvent().shiftKey);
          }
        }, this);
        this._populateCardMenu(card);
      });
    },

    __itemClicked: function(item, isShiftPressed) {
      const studiesCont = this._resourcesContainer.getFlatList();

      if (isShiftPressed) {
        const lastIdx = studiesCont.getLastSelectedIndex();
        const currentIdx = studiesCont.getIndex(item);
        const minMax = [Math.min(lastIdx, currentIdx), Math.max(lastIdx, currentIdx)];
        for (let i=minMax[0]; i<=minMax[1]; i++) {
          const card = studiesCont.getChildren()[i];
          if (card.isVisible()) {
            card.setValue(true);
          }
        }
      }
      studiesCont.setLastSelectedIndex(studiesCont.getIndex(item));

      if (!item.isMultiSelectionMode()) {
        const studyData = this.__getStudyData(item.getUuid(), false);
        this._openResourceDetails(studyData);
        this.resetSelection();
      }
    },

    __attachEventHandlers: function() {
      const socket = osparc.wrapper.WebSocket.getInstance();
      socket.on("projectStateUpdated", data => {
        if (data) {
          const studyId = data["project_uuid"];
          const state = ("data" in data) ? data.data : {};
          const errors = ("errors" in data) ? data.errors : [];
          this.__studyStateReceived(studyId, state, errors);
        }
      }, this);

      const commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.resetSelection();
        this.setMultiSelection(false);
      });
      osparc.store.Store.getInstance().addListener("changeTags", () => {
        this.invalidateStudies();
        this.__reloadStudies();
      }, this);

      qx.event.message.Bus.subscribe("reloadStudies", () => {
        this.invalidateStudies();
        this.__reloadStudies();
      }, this);
    },

    __getNextRequestParams: function() {
      if ("nextRequest" in this._resourcesContainer.getFlatList() &&
        this._resourcesContainer.getFlatList().nextRequest !== null &&
        osparc.utils.Utils.hasParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "offset") &&
        osparc.utils.Utils.hasParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "limit")
      ) {
        return {
          offset: osparc.utils.Utils.getParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "offset"),
          limit: osparc.utils.Utils.getParamFromURL(this._resourcesContainer.getFlatList().nextRequest, "limit")
        };
      }
      return null;
    },

    __getNextStudiesRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES,
          orderBy: JSON.stringify(this.getOrderBy()),
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };

      params.url.workspaceId = this.getCurrentWorkspaceId();
      params.url.folderId = this.getCurrentFolderId();
      if (params.url.orderBy) {
        return osparc.data.Resources.fetch("studies", "getPageSortBy", params, undefined, options);
      } else if (params.url.search) {
        return osparc.data.Resources.fetch("studies", "getPageSearch", params, undefined, options);
      }
      return osparc.data.Resources.fetch("studies", "getPage", params, undefined, options);
    },

    __getTextFilteredNextRequest: function(text) {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES,
          text
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };

      params.url.workspaceId = this.getCurrentWorkspaceId();
      params.url.folderId = this.getCurrentFolderId();
      return osparc.data.Resources.fetch("studies", "getPageSearch", params, undefined, options);
    },

    __getSortedByNextRequest: function() {
      const params = {
        url: {
          offset: 0,
          limit: osparc.dashboard.ResourceBrowserBase.PAGINATED_STUDIES,
          orderBy: JSON.stringify(this.getOrderBy())
        }
      };
      const nextRequestParams = this.__getNextRequestParams();
      if (nextRequestParams) {
        params.url.offset = nextRequestParams.offset;
        params.url.limit = nextRequestParams.limit;
      }
      const options = {
        resolveWResponse: true
      };

      params.url.workspaceId = this.getCurrentWorkspaceId();
      params.url.folderId = this.getCurrentFolderId();
      return osparc.data.Resources.fetch("studies", "getPageSortBy", params, undefined, options);
    },

    invalidateStudies: function() {
      osparc.store.Store.getInstance().invalidate("studies");
      this.__resetStudiesList();
      this._resourcesContainer.getFlatList().nextRequest = null;
    },

    __addNewStudyButtons: function() {
      if (this.getCurrentWorkspaceId()) {
        const currentWorkspace = osparc.store.Workspaces.getInstance().getWorkspace(this.getCurrentWorkspaceId());
        if (currentWorkspace && !currentWorkspace.getMyAccessRights()["write"]) {
          // If user can't write in workspace, do not show plus buttons
          return;
        }
      }

      switch (osparc.product.Utils.getProductName()) {
        case "osparc":
          this.__addEmptyStudyPlusButton();
          break;
        case "tis":
        case "tiplite":
          this.__addTIPPlusButtons();
          break;
        case "s4l":
        case "s4lacad":
        case "s4llite":
          this.__addPlusButtonsFromServices();
          break;
      }
    },

    __addEmptyStudyPlusButton: function() {
      const mode = this._resourcesContainer.getMode();
      const title = this.tr("Empty") + " " + osparc.product.Utils.getStudyAlias({
        firstUpperCase: true
      })
      const desc = this.tr("Start with an empty study");
      const newStudyBtn = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
      newStudyBtn.setCardKey("new-study");
      newStudyBtn.subscribeToFilterGroup("searchBarFilter");
      osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
      newStudyBtn.addListener("execute", () => this.__newStudyBtnClicked(newStudyBtn));
      if (this._resourcesContainer.getMode() === "list") {
        const width = this._resourcesContainer.getBounds().width - 15;
        newStudyBtn.setWidth(width);
      }
      this._resourcesContainer.addNonResourceCard(newStudyBtn);
    },

    __addTIPPlusButtons: function() {
      osparc.data.Resources.get("templates")
        .then(templates => {
          if (templates) {
            osparc.utils.Utils.fetchJSON("/resource/osparc/new_studies.json")
              .then(newStudiesData => {
                const product = osparc.product.Utils.getProductName()
                if (product in newStudiesData) {
                  const mode = this._resourcesContainer.getMode();
                  const title = this.tr("New Plan");
                  const desc = this.tr("Choose Plan in pop-up");
                  const newStudyBtn = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
                  newStudyBtn.setCardKey("new-study");
                  newStudyBtn.subscribeToFilterGroup("searchBarFilter");
                  osparc.utils.Utils.setIdToWidget(newStudyBtn, "newStudyBtn");
                  if (this._resourcesContainer.getMode() === "list") {
                    const width = this._resourcesContainer.getBounds().width - 15;
                    newStudyBtn.setWidth(width);
                  }
                  this._resourcesContainer.addNonResourceCard(newStudyBtn);
                  newStudyBtn.addListener("execute", () => {
                    newStudyBtn.setValue(false);

                    const newStudies = new osparc.dashboard.NewStudies(newStudiesData[product]);
                    newStudies.addListener("templatesLoaded", () => {
                      newStudies.setGroupBy("category");
                      const winTitle = this.tr("New Plan");
                      const win = osparc.ui.window.Window.popUpInWindow(newStudies, winTitle, osparc.dashboard.NewStudies.WIDTH+40, 300).set({
                        clickAwayClose: false,
                        resizable: true
                      });
                      newStudies.addListener("newStudyClicked", e => {
                        win.close();
                        const templateInfo = e.getData();
                        const templateData = templates.find(t => t.name === templateInfo.expectedTemplateLabel);
                        if (templateData) {
                          this.__newPlanBtnClicked(templateData, templateInfo.newStudyLabel);
                        }
                      });
                      osparc.utils.Utils.setIdToWidget(win, "newStudiesWindow");
                    });
                  });
                }
              });
          }
        });
    },

    __addNewStudyFromServiceButtons: function(key, newButtonInfo) {
      const versions = osparc.service.Utils.getVersions(key);
      if (versions.length && newButtonInfo) {
        // scale to latest compatible
        const latestVersion = versions[0];
        const latestCompatible = osparc.service.Utils.getLatestCompatible(key, latestVersion);
        osparc.store.Services.getService(latestCompatible["key"], latestCompatible["version"])
          .then(latestMetadata => {
            const title = newButtonInfo.title + " " + osparc.service.Utils.extractVersionDisplay(latestMetadata);
            const desc = newButtonInfo.description;
            const mode = this._resourcesContainer.getMode();
            const newStudyFromServiceButton = (mode === "grid") ? new osparc.dashboard.GridButtonNew(title, desc) : new osparc.dashboard.ListButtonNew(title, desc);
            newStudyFromServiceButton.setCardKey("new-"+key);
            osparc.utils.Utils.setIdToWidget(newStudyFromServiceButton, newButtonInfo.idToWidget);
            newStudyFromServiceButton.addListener("execute", () => this.__newStudyFromServiceBtnClicked(newStudyFromServiceButton, latestMetadata["key"], latestMetadata["version"], newButtonInfo.newStudyLabel));
            if (this._resourcesContainer.getMode() === "list") {
              const width = this._resourcesContainer.getBounds().width - 15;
              newStudyFromServiceButton.setWidth(width);
            }
            this._resourcesContainer.addNonResourceCard(newStudyFromServiceButton);
          })
      }
    },

    __addPlusButtonsFromServices: function() {
      // add new plus buttons if key services exists
      osparc.utils.Utils.fetchJSON("/resource/osparc/new_studies.json")
        .then(newStudiesData => {
          const product = osparc.product.Utils.getProductName()
          if (product in newStudiesData) {
            const newButtonsInfo = newStudiesData[product].resources;
            newButtonsInfo.forEach(newButtonInfo => {
              this.__addNewStudyFromServiceButtons(newButtonInfo.expectedKey, newButtonInfo);
            });
          }
        });
    },

    // LAYOUT //
    _createLayout: function() {
      if (osparc.utils.DisabledPlugins.isFoldersEnabled()) {
        const workspaceHeader = new osparc.dashboard.WorkspaceHeader();
        this.bind("currentWorkspaceId", workspaceHeader, "currentWorkspaceId");
        this._addToLayout(workspaceHeader);
      }

      this._createResourcesLayout();

      const containerHeader = this._resourcesContainer.getContainerHeader();
      if (containerHeader) {
        this.bind("currentWorkspaceId", containerHeader, "currentWorkspaceId", {
          onUpdate: () => containerHeader.setCurrentFolderId(null)
        });
        this.bind("currentFolderId", containerHeader, "currentFolderId");
        containerHeader.addListener("changeContext", e => {
          const {
            workspaceId,
            folderId,
          } = e.getData();
          this._changeContext(workspaceId, folderId);
        });
      }
      const list = this._resourcesContainer.getFlatList();
      if (list) {
        osparc.utils.Utils.setIdToWidget(list, "studiesList");
      }

      const importStudyButton = this.__createImportButton();
      const isDisabled = osparc.utils.DisabledPlugins.isImportDisabled();
      importStudyButton.setVisibility(isDisabled ? "excluded" : "visible");
      this._toolbar.add(importStudyButton);

      const selectStudiesButton = this.__createSelectButton();
      this._toolbar.add(selectStudiesButton);

      const studiesDeleteButton = this.__createDeleteButton(false);
      this._toolbar.add(studiesDeleteButton);

      this._toolbar.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.__addSortByButton();
      this._addViewModeButton();

      this._addResourceFilter();

      this.__addNewStudyButtons();

      const loadMoreBtn = this.__createLoadMoreButton();
      this._resourcesContainer.addNonResourceCard(loadMoreBtn);

      this.addListener("changeMultiSelection", e => {
        const multiEnabled = e.getData();
        const cards = this._resourcesContainer.getCards();
        cards.forEach(card => {
          if (!osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card)) {
            card.setEnabled(!multiEnabled);
          }
        });
        importStudyButton.setEnabled(!multiEnabled);
      });

      this._resourcesContainer.addListener("changeSelection", e => {
        const selection = e.getData();
        studiesDeleteButton.set({
          visibility: selection.length ? "visible" : "excluded",
          label: selection.length > 1 ? this.tr("Delete selected")+" ("+selection.length+")" : this.tr("Delete")
        });
      });

      this._resourcesContainer.addListener("changeVisibility", () => this._moreResourcesRequired());

      return this._resourcesContainer;
    },

    __addSortByButton: function() {
      const sortByButton = new osparc.dashboard.SortedByMenuButton();
      sortByButton.set({
        appearance: "form-button-outlined"
      });
      osparc.utils.Utils.setIdToWidget(sortByButton, "sortByButton");
      sortByButton.addListener("sortByChanged", e => {
        this.setOrderBy(e.getData())
        this.__reloadSortedByStudies();
      }, this);
      this._toolbar.add(sortByButton);
    },

    __addShowSharedWithButton: function() {
      const sharedWithButton = new osparc.dashboard.SharedWithMenuButton("study");
      sharedWithButton.set({
        appearance: "form-button-outlined"
      });
      osparc.utils.Utils.setIdToWidget(sharedWithButton, "sharedWithButton");

      sharedWithButton.addListener("sharedWith", e => {
        const option = e.getData();
        this._searchBarFilter.setSharedWithActiveFilter(option.id, option.label);
      }, this);
      this._searchBarFilter.addListener("filterChanged", e => {
        const filterData = e.getData();
        if (filterData.text) {
          this.__reloadFilteredResources(filterData.text);
        } else {
          this.__reloadFoldersAndStudies();
        }
        sharedWithButton.filterChanged(filterData);
      }, this);

      this._toolbar.add(sharedWithButton);
    },

    __createLoadMoreButton: function() {
      const mode = this._resourcesContainer.getMode();
      const loadMoreBtn = this._loadingResourcesBtn = (mode === "grid") ? new osparc.dashboard.GridButtonLoadMore() : new osparc.dashboard.ListButtonLoadMore();
      loadMoreBtn.setCardKey("load-more");
      osparc.utils.Utils.setIdToWidget(loadMoreBtn, "studiesLoading");
      loadMoreBtn.addListener("execute", () => {
        loadMoreBtn.setValue(false);
        this._moreResourcesRequired();
      });
      return loadMoreBtn;
    },

    __createImportButton: function() {
      const importButton = new qx.ui.form.Button(this.tr("Import"));
      importButton.set({
        appearance: "form-button-outlined"
      });
      importButton.addListener("execute", () => {
        const importStudy = new osparc.study.Import();
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
          const maxSize = 10 * 1000 * 1000 * 1000; // 10 GB
          if (size > maxSize) {
            osparc.FlashMessenger.logAs(`The file is too big. Maximum size is ${maxSize}MB. Please provide with a smaller file or a repository URL.`, "ERROR");
            return;
          }
          this.__importStudy(file);
        }, this);
      }, this);
      return importButton;
    },

    __createDeleteButton: function() {
      const deleteButton = new qx.ui.form.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/14").set({
        appearance: "danger-button",
        visibility: "excluded"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "deleteStudiesBtn");
      deleteButton.addListener("execute", () => {
        const selection = this._resourcesContainer.getSelection();
        const preferencesSettings = osparc.Preferences.getInstance();
        if (preferencesSettings.getConfirmDeleteStudy()) {
          const win = this.__createConfirmWindow(selection.map(button => button.getTitle()));
          win.center();
          win.open();
          win.addListener("close", () => {
            if (win.getConfirmed()) {
              this.__doDeleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
            }
          }, this);
        } else {
          this.__doDeleteStudies(selection.map(button => this.__getStudyData(button.getUuid(), false)), false);
        }
      }, this);
      return deleteButton;
    },

    __createSelectButton: function() {
      const selectButton = new qx.ui.form.ToggleButton().set({
        appearance: "form-button-outlined",
        marginRight: 8
      });
      selectButton.bind("value", this, "multiSelection");
      selectButton.bind("value", selectButton, "label", {
        converter: val => val ? this.tr("Cancel Selection") : (this.tr("Select ") + osparc.product.Utils.getStudyAlias({
          plural: true,
          firstUpperCase: true
        }))
      });
      this.bind("multiSelection", selectButton, "value");
      return selectButton;
    },

    __applyMultiSelection: function(value) {
      this._resourcesContainer.getCards().forEach(studyItem => {
        if (osparc.dashboard.ResourceBrowserBase.isCardButtonItem(studyItem)) {
          studyItem.setMultiSelectionMode(value);
          if (value === false) {
            studyItem.setValue(false);
          }
        }
      });
    },
    // LAYOUT //

    __studyStateReceived: function(studyId, state, errors) {
      osparc.store.Store.getInstance().setStudyState(studyId, state);
      const idx = this._resourcesList.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this._resourcesList[idx]["state"] = state;
      }
      const studyItem = this._resourcesContainer.getCards().find(card => osparc.dashboard.ResourceBrowserBase.isCardButtonItem(card) && card.getUuid() === studyId);
      if (studyItem) {
        studyItem.setState(state);
      }
      if (errors && errors.length) {
        console.error(errors);
      }
    },

    __newStudyBtnClicked: function(button) {
      button.setValue(false);
      const minStudyData = osparc.data.model.Study.createMinStudyObject();
      const title = osparc.utils.Utils.getUniqueStudyName(minStudyData.name, this._resourcesList);
      minStudyData["name"] = title;
      minStudyData["workspaceId"] = this.getCurrentWorkspaceId();
      minStudyData["folderId"] = this.getCurrentFolderId();
      this._showLoadingPage(this.tr("Creating ") + (minStudyData.name || osparc.product.Utils.getStudyAlias()));
      const params = {
        data: minStudyData
      };
      osparc.study.Utils.createStudyAndPoll(params)
        .then(studyData => this.__startStudyAfterCreating(studyData["uuid"]))
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __newPlanBtnClicked: function(templateData, newStudyName) {
      // do not override cached template data
      const templateCopyData = osparc.utils.Utils.deepCloneObject(templateData);
      const title = osparc.utils.Utils.getUniqueStudyName(newStudyName, this._resourcesList);
      templateCopyData.name = title;
      this._showLoadingPage(this.tr("Creating ") + (newStudyName || osparc.product.Utils.getStudyAlias()));
      const contextProps = {
        workspaceId: this.getCurrentWorkspaceId(),
        folderId: this.getCurrentFolderId(),
      };
      osparc.study.Utils.createStudyFromTemplate(templateCopyData, this._loadingPage, contextProps)
        .then(studyId => this.__startStudyAfterCreating(studyId))
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __newStudyFromServiceBtnClicked: function(button, key, version, newStudyLabel) {
      button.setValue(false);
      this._showLoadingPage(this.tr("Creating ") + osparc.product.Utils.getStudyAlias());
      const contextProps = {
        workspaceId: this.getCurrentWorkspaceId(),
        folderId: this.getCurrentFolderId(),
      };
      osparc.study.Utils.createStudyFromService(key, version, this._resourcesList, newStudyLabel, contextProps)
        .then(studyId => this.__startStudyAfterCreating(studyId))
        .catch(err => {
          this._hideLoadingPage();
          osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
          console.error(err);
        });
    },

    __startStudyAfterCreating: function(studyId) {
      const openCB = () => this._hideLoadingPage();
      const cancelCB = () => {
        this._hideLoadingPage();
        const params = {
          url: {
            studyId
          }
        };
        osparc.data.Resources.fetch("studies", "delete", params, studyId);
      };
      const isStudyCreation = true;
      this._startStudyById(studyId, openCB, cancelCB, isStudyCreation);
    },

    _updateStudyData: function(studyData) {
      studyData["resourceType"] = "study";
      const studies = this._resourcesList;
      const index = studies.findIndex(study => study["uuid"] === studyData["uuid"]);
      if (index === -1) {
        // add it in first position, most likely it's a new study
        studies.unshift(studyData);
      } else {
        studies[index] = studyData;
      }
      this._reloadCards();
    },

    __removeFromStudyList: function(studyId) {
      const idx = this._resourcesList.findIndex(study => study["uuid"] === studyId);
      if (idx > -1) {
        this._resourcesList.splice(idx, 1);
      }
      this._resourcesContainer.removeCard(studyId);
    },

    _populateCardMenu: function(card) {
      const menu = card.getMenu();
      const studyData = card.getResourceData();

      const writeAccess = osparc.data.model.Study.canIWrite(studyData["accessRights"]);
      const deleteAccess = osparc.data.model.Study.canIDelete(studyData["accessRights"]);

      const openButton = this._getOpenMenuButton(studyData);
      if (openButton) {
        menu.add(openButton);
      }

      if (writeAccess) {
        const renameStudyButton = this.__getRenameStudyMenuButton(studyData);
        menu.add(renameStudyButton);
      }

      if (writeAccess) {
        const editThumbnailButton = this.__getThumbnailStudyMenuButton(studyData);
        menu.add(editThumbnailButton);
      }

      const duplicateStudyButton = this.__getDuplicateMenuButton(studyData);
      menu.add(duplicateStudyButton);

      if (osparc.product.Utils.isProduct("osparc")) {
        const exportStudyButton = this.__getExportMenuButton(studyData);
        menu.add(exportStudyButton);
      }

      menu.addSeparator();

      // Access Rights are set at workspace level)
      if (writeAccess && this.getCurrentWorkspaceId() === null) {
        const shareButton = this._getShareMenuButton(card);
        if (shareButton) {
          menu.add(shareButton);
        }
      }

      if (writeAccess) {
        const tagsButton = this._getTagsMenuButton(card);
        if (tagsButton) {
          menu.add(tagsButton);
        }
      }

      const studyDataButton = this.__getStudyDataMenuButton(card);
      menu.add(studyDataButton);

      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const billingsSettingsButton = this.__getBillingMenuButton(card);
        menu.add(billingsSettingsButton);
      }

      if (writeAccess && osparc.utils.DisabledPlugins.isFoldersEnabled()) {
        menu.addSeparator();

        const moveToFolderButton = this.__getMoveStudyToFolderMenuButton(studyData);
        if (moveToFolderButton) {
          menu.add(moveToFolderButton);
        }

        const moveToWorkspaceButton = this.__getMoveStudyToWorkspaceMenuButton(studyData);
        if (moveToWorkspaceButton) {
          menu.add(moveToWorkspaceButton);
        }
      }

      if (deleteAccess) {
        const deleteButton = this.__getDeleteStudyMenuButton(studyData, false);
        if (deleteButton) {
          menu.addSeparator();
          menu.add(deleteButton);
        }
      }

      card.evaluateMenuButtons();
    },

    __getRenameStudyMenuButton: function(studyData) {
      const renameButton = new qx.ui.menu.Button(this.tr("Rename..."), "@FontAwesome5Solid/pencil-alt/12");
      renameButton.addListener("execute", () => {
        const renamer = new osparc.widget.Renamer(studyData["name"]);
        renamer.addListener("labelChanged", e => {
          renamer.close();
          const newLabel = e.getData()["newLabel"];
          this.__updateName(studyData, newLabel);
        }, this);
        renamer.center();
        renamer.open();
      }, this);
      return renameButton;
    },

    __getThumbnailStudyMenuButton: function(studyData) {
      const thumbButton = new qx.ui.menu.Button(this.tr("Thumbnail..."), "@FontAwesome5Solid/image/12");
      thumbButton.addListener("execute", () => {
        osparc.editor.ThumbnailSuggestions.extractThumbnailSuggestions(studyData)
          .then(suggestions => {
            const title = this.tr("Edit Thumbnail");
            const oldThumbnail = studyData.thumbnail;
            const thumbnailEditor = new osparc.editor.ThumbnailEditor(oldThumbnail, suggestions);
            const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, suggestions.length > 2 ? 500 : 350, 280);
            thumbnailEditor.addListener("updateThumbnail", e => {
              win.close();
              const newUrl = e.getData();
              this.__updateThumbnail(studyData, newUrl);
            }, this);
            thumbnailEditor.addListener("cancel", () => win.close());
          })
          .catch(err => console.error(err));
      }, this);
      return thumbButton;
    },

    __updateName: function(studyData, name) {
      osparc.info.StudyUtils.patchStudyData(studyData, "name", name)
        .then(() => this._updateStudyData(studyData))
        .catch(err => {
          console.error(err);
          const msg = this.tr("Something went wrong Renaming");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __updateThumbnail: function(studyData, url) {
      osparc.info.StudyUtils.patchStudyData(studyData, "thumbnail", url)
        .then(() => this._updateStudyData(studyData))
        .catch(err => {
          console.error(err);
          const msg = this.tr("Something went wrong updating the Thumbnail");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __getStudyDataMenuButton: function(card) {
      const text = osparc.utils.Utils.capitalize(osparc.product.Utils.getStudyAlias()) + this.tr(" files...");
      const studyDataButton = new qx.ui.menu.Button(text, "@FontAwesome5Solid/file/12");
      studyDataButton["studyDataButton"] = true;
      studyDataButton.addListener("tap", () => card.openData(), this);
      return studyDataButton;
    },

    __getBillingMenuButton: function(card) {
      const text = osparc.utils.Utils.capitalize(this.tr("Billing Settings..."));
      const studyBillingSettingsButton = new qx.ui.menu.Button(text);
      studyBillingSettingsButton.addListener("tap", () => card.openBilling(), this);
      return studyBillingSettingsButton;
    },

    __getMoveStudyToFolderMenuButton: function(studyData) {
      const text = this.tr("Move to Folder...");
      const moveToFolderButton = new qx.ui.menu.Button(text, "@FontAwesome5Solid/folder/12");
      moveToFolderButton["moveToFolderButton"] = true;
      moveToFolderButton.addListener("tap", () => {
        const title = this.tr("Move") + " " + studyData["name"];
        const moveStudyToFolder = new osparc.dashboard.MoveResourceToFolder(this.getCurrentFolderId(), this.getCurrentWorkspaceId());
        const win = osparc.ui.window.Window.popUpInWindow(moveStudyToFolder, title, 350, 280);
        moveStudyToFolder.addListener("moveToFolder", e => {
          win.close();
          const destFolderId = e.getData();
          const params = {
            url: {
              studyId: studyData["uuid"],
              folderId: destFolderId,
            }
          };
          osparc.data.Resources.fetch("studies", "moveToFolder", params)
            .then(() => {
              studyData["folderId"] = destFolderId;
              this.__removeFromStudyList(studyData["uuid"]);
            })
            .catch(err => {
              console.error(err);
              osparc.FlashMessenger.logAs(err.message, "ERROR");
            });
        }, this);
        moveStudyToFolder.addListener("cancel", () => win.close());
      }, this);
      return moveToFolderButton;
    },

    __getMoveStudyToWorkspaceMenuButton: function(studyData) {
      const text = this.tr("Move to Workspace...");
      const moveToWorkspaceButton = new qx.ui.menu.Button(text, osparc.store.Workspaces.iconPath(14));
      moveToWorkspaceButton["moveToWorkspaceButton"] = true;
      moveToWorkspaceButton.addListener("tap", () => {
        const title = this.tr("Move") + " " + studyData["name"];
        const moveStudyToWorkspace = new osparc.dashboard.MoveResourceToWorkspace(this.getCurrentWorkspaceId());
        const win = osparc.ui.window.Window.popUpInWindow(moveStudyToWorkspace, title, 350, 280);
        moveStudyToWorkspace.addListener("moveToWorkspace", e => {
          win.close();
          const destWorkspaceId = e.getData();
          const confirmationWin = this.__showMoveToWorkspaceWarningMessage();
          confirmationWin.addListener("close", () => {
            if (confirmationWin.getConfirmed()) {
              const params = {
                url: {
                  studyId: studyData["uuid"],
                  workspaceId: destWorkspaceId,
                }
              };
              osparc.data.Resources.fetch("studies", "moveToWorkspace", params)
                .then(() => {
                  studyData["workspaceId"] = destWorkspaceId;
                  this.__removeFromStudyList(studyData["uuid"]);
                })
                .catch(err => {
                  console.error(err);
                  osparc.FlashMessenger.logAs(err.message, "ERROR");
                });
            }
          }, this);
        }, this);
        moveStudyToWorkspace.addListener("cancel", () => win.close());
      }, this);
      return moveToWorkspaceButton;
    },

    __getDuplicateMenuButton: function(studyData) {
      const duplicateButton = new qx.ui.menu.Button(this.tr("Duplicate"), "@FontAwesome5Solid/copy/12");
      duplicateButton["duplicateButton"] = true;
      duplicateButton.addListener("execute", () => this.__duplicateStudy(studyData), this);
      return duplicateButton;
    },

    __getExportMenuButton: function(studyData) {
      const exportButton = new qx.ui.menu.Button(this.tr("Export cMIS"), "@FontAwesome5Solid/cloud-download-alt/12");
      exportButton["exportCMISButton"] = true;
      const isDisabled = osparc.utils.DisabledPlugins.isExportDisabled();
      exportButton.setVisibility(isDisabled ? "excluded" : "visible");
      exportButton.addListener("execute", () => this.__exportStudy(studyData), this);
      return exportButton;
    },

    _deleteResourceRequested: function(studyId) {
      this.__deleteStudyRequested(this.__getStudyData(studyId));
    },

    __deleteStudyRequested: function(studyData) {
      const preferencesSettings = osparc.Preferences.getInstance();
      if (preferencesSettings.getConfirmDeleteStudy()) {
        const win = this.__createConfirmWindow([studyData.name]);
        win.center();
        win.open();
        win.addListener("close", () => {
          if (win.getConfirmed()) {
            this.__doDeleteStudy(studyData);
          }
        }, this);
      } else {
        this.__doDeleteStudy(studyData);
      }
    },

    __getDeleteStudyMenuButton: function(studyData) {
      const deleteButton = new qx.ui.menu.Button(this.tr("Delete"), "@FontAwesome5Solid/trash/12");
      deleteButton["deleteButton"] = true;
      deleteButton.set({
        appearance: "menu-button"
      });
      osparc.utils.Utils.setIdToWidget(deleteButton, "studyItemMenuDelete");
      deleteButton.addListener("execute", () => this.__deleteStudyRequested(studyData), this);
      return deleteButton;
    },

    __getStudyData: function(id) {
      return this._resourcesList.find(study => study.uuid === id);
    },

    __createDuplicateCard: function(studyName) {
      const isGrid = this._resourcesContainer.getMode() === "grid";
      const duplicatingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      duplicatingStudyCard.buildLayout(
        this.tr("Duplicating ") + studyName,
        osparc.task.Duplicate.ICON + (isGrid ? "60" : "24"),
        null,
        true
      );

      if (this._resourcesContainer.getMode() === "list") {
        const width = this._resourcesContainer.getBounds().width - 15;
        duplicatingStudyCard.setWidth(width);
      }
      return duplicatingStudyCard;
    },

    __duplicateStudy: function(studyData) {
      const text = this.tr("Duplicate process started and added to the background tasks");
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

      const params = {
        url: {
          "studyId": studyData["uuid"]
        }
      };
      const fetchPromise = osparc.data.Resources.fetch("studies", "duplicate", params, null, {"pollTask": true});
      const interval = 1000;
      const pollTasks = osparc.data.PollTasks.getInstance();
      pollTasks.createPollingTask(fetchPromise, interval)
        .then(task => this.__taskDuplicateReceived(task, studyData["name"]))
        .catch(errMsg => {
          const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
          osparc.FlashMessenger.logAs(msg, "ERROR");
        });
    },

    __exportStudy: function(studyData) {
      const exportTask = new osparc.task.Export(studyData);
      exportTask.start();
      exportTask.setSubtitle(this.tr("Preparing files"));
      const text = this.tr("Exporting process started and added to the background tasks");
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

      const url = window.location.href + "v0/projects/" + studyData["uuid"] + ":xport";
      const progressCB = () => {
        const textSuccess = this.tr("Download started");
        exportTask.setSubtitle(textSuccess);
      };
      osparc.utils.Utils.downloadLink(url, "POST", null, progressCB)
        .catch(e => {
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(e.response)) || this.tr("Something went wrong Exporting the study");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        })
        .finally(() => {
          exportTask.stop();
        });
    },

    __importStudy: function(file) {
      const uploadingLabel = this.tr("Uploading file");
      const importTask = new osparc.task.Import();
      importTask.start();
      importTask.setSubtitle(uploadingLabel);

      const text = this.tr("Importing process started and added to the background tasks");
      osparc.FlashMessenger.getInstance().logAs(text, "INFO");

      const isGrid = this._resourcesContainer.getMode() === "grid";
      const importingStudyCard = isGrid ? new osparc.dashboard.GridButtonPlaceholder() : new osparc.dashboard.ListButtonPlaceholder();
      importingStudyCard.buildLayout(
        this.tr("Importing Study..."),
        "@FontAwesome5Solid/cloud-upload-alt/" + (isGrid ? "60" : "24"),
        uploadingLabel,
        true
      );
      importingStudyCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addNonResourceCard(importingStudyCard);

      const body = new FormData();
      body.append("fileName", file);

      const req = new XMLHttpRequest();
      req.upload.addEventListener("progress", ep => {
        // updateProgress
        if (ep.lengthComputable) {
          const percentComplete = ep.loaded / ep.total * 100;
          importingStudyCard.getChildControl("progress-bar").setValue(percentComplete);
          if (percentComplete === 100) {
            const processingLabel = this.tr("Processing study");
            importingStudyCard.getChildControl("state-label").setValue(processingLabel);
            importTask.setSubtitle(processingLabel);
            importingStudyCard.getChildControl("progress-bar").exclude();
          }
        } else {
          console.log("Unable to compute progress information since the total size is unknown");
        }
      }, false);
      req.addEventListener("load", e => {
        // transferComplete
        if (req.status == 200) {
          const processingLabel = this.tr("Processing study");
          importingStudyCard.getChildControl("state-label").setValue(processingLabel);
          importTask.setSubtitle(processingLabel);
          importingStudyCard.getChildControl("progress-bar").exclude();
          const data = JSON.parse(req.responseText);
          const params = {
            url: {
              "studyId": data["data"]["uuid"]
            }
          };
          osparc.data.Resources.getOne("studies", params)
            .then(studyData => this._updateStudyData(studyData))
            .catch(err => {
              console.error(err);
              const msg = this.tr("Something went wrong Fetching the study");
              osparc.FlashMessenger.logAs(msg, "ERROR");
            })
            .finally(() => {
              importTask.stop();
              this._resourcesContainer.removeNonResourceCard(importingStudyCard);
            });
        } else if (req.status == 400) {
          importTask.stop();
          this._resourcesContainer.removeNonResourceCard(importingStudyCard);
          const msg = osparc.data.Resources.getErrorMsg(JSON.parse(req.response)) || this.tr("Something went wrong Importing the study");
          osparc.FlashMessenger.logAs(msg, "ERROR");
        }
      });
      req.addEventListener("error", e => {
        // transferFailed
        importTask.stop();
        this._resourcesContainer.removeNonResourceCard(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.FlashMessenger.logAs(msg, "ERROR");
      });
      req.addEventListener("abort", e => {
        // transferAborted
        importTask.stop();
        this._resourcesContainer.removeNonResourceCard(importingStudyCard);
        const msg = osparc.data.Resources.getErrorMsg(e) || this.tr("Something went wrong Importing the study");
        osparc.FlashMessenger.logAs(msg, "ERROR");
      });
      req.open("POST", "/v0/projects:import", true);
      req.send(body);
    },

    __doDeleteStudy: function(studyData) {
      const myGid = osparc.auth.Data.getInstance().getGroupId();
      const collabGids = Object.keys(studyData["accessRights"]);
      const amICollaborator = collabGids.indexOf(myGid) > -1;

      let operationPromise = null;
      if (collabGids.length > 1 && amICollaborator) {
        const arCopy = osparc.utils.Utils.deepCloneObject(studyData["accessRights"]);
        // remove collaborator
        delete arCopy[myGid];
        operationPromise = osparc.info.StudyUtils.patchStudyData(studyData, "accessRights", arCopy);
      } else {
        // delete study
        operationPromise = osparc.store.Store.getInstance().deleteStudy(studyData.uuid);
      }
      operationPromise
        .then(() => this.__removeFromStudyList(studyData.uuid))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.getInstance().logAs(err, "ERROR");
        })
        .finally(() => this.resetSelection());
    },

    __doDeleteStudies: function(studiesData) {
      studiesData.forEach(studyData => this.__doDeleteStudy(studyData));
    },

    __createConfirmWindow: function(studyNames) {
      const rUSure = this.tr("Are you sure you want to delete ");
      const msg = studyNames.length > 1 ? rUSure + studyNames.length + this.tr(" studies?") : rUSure + "<b>" + studyNames[0] + "</b>?";
      const confirmationWin = new osparc.ui.window.Confirmation(msg).set({
        confirmText: this.tr("Delete"),
        confirmAction: "delete"
      });
      osparc.utils.Utils.setIdToWidget(confirmationWin.getConfirmButton(), "confirmDeleteStudyBtn");
      return confirmationWin;
    },

    // TASKS //
    __tasksReceived: function(tasks) {
      tasks.forEach(taskData => this._taskDataReceived(taskData));
    },

    _taskDataReceived: function(taskData) {
      // a bit hacky
      if (taskData["task_id"].includes("from_study") && !taskData["task_id"].includes("as_template")) {
        const interval = 1000;
        const pollTasks = osparc.data.PollTasks.getInstance();
        const task = pollTasks.addTask(taskData, interval);
        if (task === null) {
          return;
        }
        // ask backend for studyData?
        const studyName = "";
        this.__taskDuplicateReceived(task, studyName);
      }
    },

    __taskDuplicateReceived: function(task, studyName) {
      const duplicateTaskUI = new osparc.task.Duplicate(studyName);
      duplicateTaskUI.setTask(task);
      duplicateTaskUI.start();
      const duplicatingStudyCard = this.__createDuplicateCard(studyName);
      duplicatingStudyCard.setTask(task);
      duplicatingStudyCard.subscribeToFilterGroup("searchBarFilter");
      this._resourcesContainer.addNonResourceCard(duplicatingStudyCard);
      this.__attachDuplicateEventHandler(task, duplicateTaskUI, duplicatingStudyCard);
    },

    __attachDuplicateEventHandler: function(task, taskUI, duplicatingStudyCard) {
      const finished = (msg, msgLevel) => {
        if (msg) {
          osparc.FlashMessenger.logAs(msg, msgLevel);
        }
        taskUI.stop();
        this._resourcesContainer.removeNonResourceCard(duplicatingStudyCard);
      };

      task.addListener("taskAborted", () => {
        const msg = this.tr("Duplication cancelled");
        finished(msg, "INFO");
      });
      task.addListener("resultReceived", e => {
        finished();
        const duplicatedStudyData = e.getData();
        this._updateStudyData(duplicatedStudyData);
      });
      task.addListener("pollingError", e => {
        const errMsg = e.getData();
        const msg = this.tr("Something went wrong Duplicating the study<br>") + errMsg;
        finished(msg, "ERROR");
      });
    }
    // TASKS //
  }
});
