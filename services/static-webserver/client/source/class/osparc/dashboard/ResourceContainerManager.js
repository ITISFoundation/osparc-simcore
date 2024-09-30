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

qx.Class.define("osparc.dashboard.ResourceContainerManager", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.set({
      paddingBottom: 60
    });

    this.__foldersList = [];
    this.__workspacesList = [];
    this.__resourcesList = [];
    this.__groupedContainersList = [];

    const containerHeader = this.__containerHeader = new osparc.dashboard.ContextBreadcrumbs();
    this._add(containerHeader);
    containerHeader.setVisibility(osparc.utils.DisabledPlugins.isFoldersEnabled() ? "visible" : "excluded");


    const workspacesContainer = this.__workspacesContainer = new osparc.dashboard.ToggleButtonContainer();
    workspacesContainer.setVisibility(osparc.utils.DisabledPlugins.isFoldersEnabled() ? "visible" : "excluded");


    const foldersContainer = this.__foldersContainer = new osparc.dashboard.ToggleButtonContainer();
    this._add(foldersContainer);
    foldersContainer.setVisibility(osparc.utils.DisabledPlugins.isFoldersEnabled() ? "visible" : "excluded");

    const nonGroupedContainer = this.__nonGroupedContainer = new osparc.dashboard.ToggleButtonContainer();
    [
      "changeSelection",
      "changeVisibility"
    ].forEach(signalName => {
      nonGroupedContainer.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
    });
    this._add(nonGroupedContainer);

    const groupedContainers = this.__groupedContainers = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this._add(groupedContainers);
  },

  properties: {
    mode: {
      check: ["grid", "list"],
      init: "grid",
      nullable: false,
      event: "changeMode",
      apply: "reloadCards"
    },

    groupBy: {
      check: [null, "tags", "shared"],
      init: null,
      nullable: true
    }
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data",
    "tagClicked": "qx.event.type.Data",
    "emptyStudyClicked": "qx.event.type.Data",
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data",
    "folderSelected": "qx.event.type.Data",
    "folderUpdated": "qx.event.type.Data",
    "moveFolderToFolderRequested": "qx.event.type.Data",
    "moveFolderToWorkspaceRequested": "qx.event.type.Data",
    "deleteFolderRequested": "qx.event.type.Data",
    "workspaceSelected": "qx.event.type.Data",
    "workspaceUpdated": "qx.event.type.Data",
    "deleteWorkspaceRequested": "qx.event.type.Data",
  },

  statics: {
    sortListByPriority: function(list) {
      list.getChildren().sort((a, b) => {
        let sortingValue = a.getPriority() - b.getPriority();
        return sortingValue;
      });
    },

    cardExists: function(container, newCard) {
      const cardKey = newCard.isPropertyInitialized("cardKey") ? newCard.getCardKey() : null;
      if (cardKey) {
        const idx = container.getChildren().findIndex(card => card.isPropertyInitialized("cardKey") && newCard.getCardKey() === card.getCardKey());
        if (idx > -1) {
          return true;
        }
      }
      return false;
    }
  },

  members: {
    __foldersList: null,
    __workspacesList: null,
    __resourcesList: null,
    __groupedContainersList: null,
    __foldersLayout: null,
    __containerHeader: null,
    __foldersContainer: null,
    __workspacesContainer: null,
    __nonGroupedContainer: null,
    __groupedContainers: null,

    addNonResourceCard: function(card) {
      if (card instanceof qx.ui.form.ToggleButton) {
        if (this.getGroupBy()) {
          // it will always go to the no-group group
          const noGroupContainer = this.__getGroupContainer("no-group");
          this.__addCardToContainer(card, noGroupContainer);
          this.self().sortListByPriority(noGroupContainer.getContentContainer());
        } else {
          this.__addCardToContainer(card, this.__nonGroupedContainer);
          this.self().sortListByPriority(this.__nonGroupedContainer);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    removeNonResourceCard: function(card) {
      if (card instanceof qx.ui.form.ToggleButton) {
        if (this.getGroupBy()) {
          const noGroupContainer = this.__getGroupContainer("no-group");
          if (noGroupContainer.getContentContainer().getChildren().indexOf(card) > -1) {
            noGroupContainer.getContentContainer().remove(card);
          }
        } else if (this.__nonGroupedContainer.getChildren().indexOf(card) > -1) {
          this.__nonGroupedContainer.remove(card);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    removeCard: function(uuid) {
      if (this.getGroupBy()) {
        this.__groupedContainersList.forEach(groupedContainer => groupedContainer.removeCard(uuid));
      } else {
        this.__nonGroupedContainer.removeCard(uuid);
      }
    },

    getContainerHeader: function() {
      return this.__containerHeader;
    },

    getFlatList: function() {
      return this.__nonGroupedContainer;
    },

    __createGroupContainer: function(groupId, headerLabel, headerColor = "text") {
      const groupContainer = new osparc.dashboard.GroupedToggleButtonContainer().set({
        groupId: groupId.toString(),
        headerLabel,
        headerIcon: "",
        headerColor,
        visibility: "excluded"
      });
      this.__groupedContainersList.push(groupContainer);
      return groupContainer;
    },

    areMoreResourcesRequired: function(loadingResourcesBtn) {
      if (this.__nonGroupedContainer) {
        return this.__nonGroupedContainer.areMoreResourcesRequired(loadingResourcesBtn);
      }
      // If containers are grouped all the resources are expected to be fetched
      return false;
    },

    getCards: function() {
      if (this.__nonGroupedContainer) {
        return this.__nonGroupedContainer.getChildren();
      }
      const cards = [];
      this.__groupedContainersList.forEach(groupedContainer => cards.push(...groupedContainer.getCards()));
      return cards;
    },

    getSelection: function() {
      if (this.getGroupBy() === null) {
        return this.__nonGroupedContainer.getSelection();
      }
      return [];
    },

    resetSelection: function() {
      if (this.getGroupBy() === null) {
        this.__nonGroupedContainer.resetSelection();
      }
    },

    __getGroupContainer: function(gid) {
      const idx = this.__groupedContainersList.findIndex(groupContainer => groupContainer.getGroupId() === gid.toString());
      if (idx > -1) {
        return this.__groupedContainersList[idx];
      }
      return null;
    },

    __createCard: function(resourceData) {
      const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];
      const card = this.getMode() === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      card.set({
        appearance: resourceData.type ? `pb-${resourceData.type}` : `pb-${resourceData.resourceType}`,
        resourceData: resourceData,
        tags
      });
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });
      card.setMenu(menu);
      card.subscribeToFilterGroup("searchBarFilter");

      [
        "updateStudy",
        "updateTemplate",
        "updateService",
        "publishTemplate",
        "tagClicked",
        "emptyStudyClicked"
      ].forEach(eName => card.addListener(eName, e => this.fireDataEvent(eName, e.getData())));
      return card;
    },

    __addCardToContainer: function(card, container) {
      container.add(card);

      if (this.getMode() === "list") {
        [
          "appear",
          "resize",
        ].forEach(ev => {
          container.addListener(ev, () => {
            const bounds = container.getBounds() || container.getSizeHint();
            card.setWidth(bounds.width);
          });
        });
      }
    },

    setResourcesToList: function(resourcesList) {
      this.__resourcesList = resourcesList;
    },

    __cleanAll: function() {
      if (this.__workspacesContainer) {
        this.__workspacesContainer.removeAll();
      }
      if (this.__nonGroupedContainer) {
        this.__nonGroupedContainer.removeAll();
        this.__nonGroupedContainer = null;
      }
      if (this.__groupedContainers) {
        this.__groupedContainers.removeAll();
      }
      this.__groupedContainersList.forEach(groupedContainer => {
        groupedContainer.getContentContainer().removeAll();
      });
      this.__groupedContainersList = [];
      this._removeAll();
    },

    reloadCards: function(resourceType) {
      this.__cleanAll();
      if (resourceType === "studies") {
        this._add(this.__containerHeader);
        this._add(this.__foldersContainer);
      }
      if (this.getGroupBy()) {
        const noGroupContainer = this.__createGroupContainer("no-group", "No Group", "transparent");
        this.__groupedContainers.add(noGroupContainer);
        this._add(this.__groupedContainers);
      } else {
        const flatList = this.__nonGroupedContainer = new osparc.dashboard.ToggleButtonContainer();
        osparc.utils.Utils.setIdToWidget(flatList, resourceType + "List");
        [
          "changeSelection",
          "changeVisibility"
        ].forEach(signalName => {
          flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
        });
        const spacing = this.getMode() === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
        this.__nonGroupedContainer.getLayout().set({
          spacingX: spacing,
          spacingY: spacing
        });
        this._add(this.__nonGroupedContainer);
      }

      let cards = [];
      this.__resourcesList.forEach(resourceData => {
        Array.prototype.push.apply(cards, this.__resourceToCards(resourceData));
      });
      return cards;
    },

    reloadNewCards: function() {
      let newCards = [];
      const currentCards = this.getCards();
      this.__resourcesList.forEach(resourceData => {
        const idx = currentCards.findIndex(card => card.isPropertyInitialized("uuid") && resourceData["uuid"] === card.getUuid());
        if (idx === -1) {
          Array.prototype.push.apply(newCards, this.__resourceToCards(resourceData));
        }
      });
      return newCards;
    },

    // WORKSPACES
    setWorkspacesToList: function(workspacesList) {
      this.__workspacesList = workspacesList;
    },

    reloadWorkspaces: function() {
      this.__cleanAll();
      this._add(this.__containerHeader);
      this._add(this.__workspacesContainer);
      let workspacesCards = [];
      this.__workspacesList.forEach(workspaceData => workspacesCards.push(this.__workspaceToCard(workspaceData)));
      return workspacesCards;
    },

    addNewWorkspaceCard: function(newWorkspaceCard) {
      this.__workspacesContainer.addAt(newWorkspaceCard, 0);
    },

    __workspaceToCard: function(workspaceData) {
      const card = this.__createWorkspaceCard(workspaceData);
      this.__workspacesContainer.add(card);
      return card;
    },

    __createWorkspaceCard: function(workspace) {
      const card = new osparc.dashboard.WorkspaceButtonItem(workspace);
      card.subscribeToFilterGroup("searchBarFilter");
      [
        "workspaceSelected",
        "workspaceUpdated",
        "deleteWorkspaceRequested",
      ].forEach(eName => card.addListener(eName, e => this.fireDataEvent(eName, e.getData())));
      return card;
    },
    // /WORKSPACES

    // FOLDERS
    setFoldersToList: function(foldersList) {
      this.__foldersList = foldersList;
    },

    reloadFolders: function() {
      if (this.__foldersContainer) {
        this.__foldersContainer.removeAll();
      }
      let folderCards = [];
      this.__foldersList.forEach(folderData => folderCards.push(this.__folderToCard(folderData)));
      return folderCards;
    },

    addNewFolderCard: function(newFolderCard) {
      this.__foldersContainer.addAt(newFolderCard, 0);
    },

    __folderToCard: function(folderData) {
      const card = this.__createFolderCard(folderData);
      this.__foldersContainer.add(card);
      return card;
    },

    __createFolderCard: function(folder) {
      const card = new osparc.dashboard.FolderButtonItem(folder);
      card.subscribeToFilterGroup("searchBarFilter");
      [
        "folderSelected",
        "folderUpdated",
        "moveFolderToFolderRequested",
        "moveFolderToWorkspaceRequested",
        "deleteFolderRequested",
      ].forEach(eName => card.addListener(eName, e => this.fireDataEvent(eName, e.getData())));
      return card;
    },
    // /FOLDERS

    __moveNoGroupToLast: function() {
      const idx = this.__groupedContainers.getChildren().findIndex(grpContainer => grpContainer === this.__getGroupContainer("no-group"));
      if (idx > -1) {
        this.__groupedContainers.getChildren().push(this.__groupedContainers.getChildren().splice(idx, 1)[0]);
      }
    },

    __groupByTags: function(cards, resourceData) {
      const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];
      if (tags.length === 0) {
        let noGroupContainer = this.__getGroupContainer("no-group");
        const card = this.__createCard(resourceData);
        this.__addCardToContainer(card, noGroupContainer);
        this.self().sortListByPriority(noGroupContainer.getContentContainer());
        cards.push(card);
      } else {
        tags.forEach(tag => {
          let groupContainer = this.__getGroupContainer(tag.id);
          if (groupContainer === null) {
            groupContainer = this.__createGroupContainer(tag.id, tag.name, tag.color);
            groupContainer.setHeaderIcon("@FontAwesome5Solid/tag/24");
            this.__groupedContainers.add(groupContainer);
            this.__groupedContainers.getChildren().sort((a, b) => a.getHeaderLabel().localeCompare(b.getHeaderLabel()));
            this.__moveNoGroupToLast();
          }
          const card = this.__createCard(resourceData);
          this.__addCardToContainer(card, groupContainer);
          this.self().sortListByPriority(groupContainer.getContentContainer());
          cards.push(card);
        });
      }
    },

    __groupByShareWith: function(cards, resourceData) {
      const orgIds = resourceData.accessRights ? Object.keys(resourceData["accessRights"]) : [];
      if (orgIds.length === 0) {
        let noGroupContainer = this.__getGroupContainer("no-group");
        const card = this.__createCard(resourceData);
        this.__addCardToContainer(card, noGroupContainer);
        this.self().sortListByPriority(noGroupContainer.getContentContainer());
        cards.push(card);
      } else {
        orgIds.forEach(orgId => {
          let groupContainer = this.__getGroupContainer(orgId);
          if (groupContainer === null) {
            groupContainer = this.__createGroupContainer(orgId, "loading-label");
            osparc.store.Store.getInstance().getOrganizationOrUser(orgId)
              .then(org => {
                if (org && org["collabType"] !== 2) {
                  let icon = "";
                  if (org.thumbnail) {
                    icon = org.thumbnail;
                  } else if (org["collabType"] === 0) {
                    icon = "@FontAwesome5Solid/globe/24";
                  } else if (org["collabType"] === 1) {
                    icon = "@FontAwesome5Solid/users/24";
                  }
                  groupContainer.set({
                    headerIcon: icon,
                    headerLabel: org.label
                  });
                } else {
                  groupContainer.exclude();
                }
              })
              .finally(() => {
                this._add(groupContainer);
                this.__moveNoGroupToLast();
              });
          }
          const card = this.__createCard(resourceData);
          this.__addCardToContainer(card, groupContainer);
          this.self().sortListByPriority(groupContainer.getContentContainer());
          cards.push(card);
        });
      }
    },

    __resourceToCards: function(resourceData) {
      const cardsCreated = [];
      if (this.getGroupBy() === "tags") {
        this.__groupByTags(cardsCreated, resourceData);
      } else if (this.getGroupBy() === "shared") {
        this.__groupByShareWith(cardsCreated, resourceData);
      } else {
        const card = this.__createCard(resourceData);
        this.__addCardToContainer(card, this.__nonGroupedContainer);
        this.self().sortListByPriority(this.__nonGroupedContainer);
        cardsCreated.push(card);
      }
      return cardsCreated;
    }
  }
});
