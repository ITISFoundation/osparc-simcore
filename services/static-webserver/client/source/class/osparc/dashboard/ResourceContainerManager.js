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

  construct: function(resourceType) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    this.set({
      paddingBottom: 60
    });

    this.__workspacesList = [];
    this.__foldersList = [];
    this.__resourcesList = [];
    this.__groupedContainersList = [];
    this.__resourceType = resourceType || "study";

    if (resourceType === "study") {
      const workspacesContainer = this.__workspacesContainer = new osparc.dashboard.CardContainer();
      this.__workspacesContainer.exclude();
      this._add(workspacesContainer);

      const foldersContainer = this.__foldersContainer = new osparc.dashboard.CardContainer();
      this.__foldersContainer.exclude();
      this._add(foldersContainer);
    }

    const noResourcesFound = this.__noResourcesFound = new qx.ui.basic.Label("No resources found").set({
      visibility: "excluded",
      font: "text-14"
    });
    noResourcesFound.exclude();
    this._add(noResourcesFound);

    const nonGroupedContainer = this.__nonGroupedContainer = this.__createFlatList();
    this._add(nonGroupedContainer);

    const groupedContainers = this.__groupedContainers = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
    this._add(groupedContainers);
  },

  properties: {
    mode: {
      check: ["grid", "list"],
      init: "grid",
      nullable: false,
      event: "changeMode"
    },

    groupBy: {
      check: [null, "tags", "shared", "groupedServices"],
      init: null,
      nullable: true
    }
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTemplate": "qx.event.type.Data",
    "updateTutorial": "qx.event.type.Data",
    "updateService": "qx.event.type.Data",
    "updateHypertool": "qx.event.type.Data",
    "publishTemplate": "qx.event.type.Data",
    "tagClicked": "qx.event.type.Data",
    "emptyStudyClicked": "qx.event.type.Data",
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data",
    "folderSelected": "qx.event.type.Data",
    "folderUpdated": "qx.event.type.Data",
    "moveFolderToRequested": "qx.event.type.Data",
    "trashFolderRequested": "qx.event.type.Data",
    "untrashFolderRequested": "qx.event.type.Data",
    "deleteFolderRequested": "qx.event.type.Data",
    "workspaceSelected": "qx.event.type.Data",
    "workspaceUpdated": "qx.event.type.Data",
    "trashWorkspaceRequested": "qx.event.type.Data",
    "untrashWorkspaceRequested": "qx.event.type.Data",
    "deleteWorkspaceRequested": "qx.event.type.Data",
    "changeContext": "qx.event.type.Data",
    "studyToFolderRequested": "qx.event.type.Data",
    "folderToFolderRequested": "qx.event.type.Data",
  },

  statics: {
    sortListByPriority: function(list) {
      if (list) {
        list.getChildren().sort((a, b) => {
          let sortingValue = a.getPriority() - b.getPriority();
          return sortingValue;
        });
      }
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
    },

    updateSpacing: function(mode, container) {
      const spacing = mode === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
      container.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
    },
  },

  members: {
    __foldersList: null,
    __workspacesList: null,
    __resourcesList: null,
    __groupedContainersList: null,
    __foldersContainer: null,
    __workspacesContainer: null,
    __nonGroupedContainer: null,
    __groupedContainers: null,
    __resourceType: null,
    __noResourcesFound: null,
    __noResourcesFoundTimer: null,

    __evaluateNoResourcesFoundLabel: function() {
      let text = null;
      switch (this.__resourceType) {
        case "study": {
          const studyBrowserContext = osparc.store.Store.getInstance().getStudyBrowserContext();
          switch (studyBrowserContext) {
            case osparc.dashboard.StudyBrowser.CONTEXT.PROJECTS:
            case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PROJECTS:
            case osparc.dashboard.StudyBrowser.CONTEXT.TRASH:
              text = this.tr("No Projects found");
              break;
            case osparc.dashboard.StudyBrowser.CONTEXT.TEMPLATES:
            case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_TEMPLATES:
              text = this.tr("No Templates found");
              break;
            case osparc.dashboard.StudyBrowser.CONTEXT.PUBLIC_TEMPLATES:
            case osparc.dashboard.StudyBrowser.CONTEXT.SEARCH_PUBLIC_TEMPLATES:
              text = this.tr("No Public Projects found");
              break;
          }
          break;
        }
        case "template":
          text = this.tr("No Tutorials found");
          break;
        case "service":
          text = this.tr("No Apps found");
          break;
        default:
          text = this.tr("No Resources found");
          break;
      }

      this.__noResourcesFound.exclude();
      if (this.__noResourcesFoundTimer) {
        clearTimeout(this.__noResourcesFoundTimer);
      }
      if (text && this.__resourcesList.length === 0) {
        // delay it a bit to avoid the initial flickering
        this.__noResourcesFoundTimer = setTimeout(() => {
          this.__noResourcesFound.set({
            value: text,
            visibility: "visible",
          });
        }, 2000);
      }
    },

    addNonResourceCard: function(card) {
      if (osparc.dashboard.CardContainer.isValidCard(card)) {
        let groupContainer = null;
        let contentContainer = null;
        if (this.getGroupBy()) {
          // it will always go to the no-group group
          groupContainer = this.__getGroupContainer("no-group");
          contentContainer = groupContainer.getContentContainer();
        } else {
          groupContainer = this.__nonGroupedContainer;
          contentContainer = this.__nonGroupedContainer;
        }
        this.__addCardToContainer(card, groupContainer);
        this.self().sortListByPriority(contentContainer);
      } else {
        console.error("CardContainer only allows CardBase as its children.");
      }
    },

    removeNonResourceCard: function(card) {
      if (osparc.dashboard.CardContainer.isValidCard(card)) {
        let contentContainer = null;
        if (this.getGroupBy()) {
          const noGroupContainer = this.__getGroupContainer("no-group");
          contentContainer = noGroupContainer.getContentContainer();
        } else {
          contentContainer = this.__nonGroupedContainer;
        }
        if (contentContainer && contentContainer.getChildren().indexOf(card) > -1) {
          contentContainer.remove(card);
        }
      } else {
        console.error("CardContainer only allows CardBase as its children.");
      }
    },

    removeCard: function(uuid) {
      if (this.getGroupBy()) {
        this.__groupedContainersList.forEach(groupedContainer => groupedContainer.removeCard(uuid));
      } else {
        this.__nonGroupedContainer.removeCard(uuid);
      }
    },

    getFlatList: function() {
      return this.__nonGroupedContainer;
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
      if (this.getGroupBy() === null && this.__nonGroupedContainer) {
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
      const tags = resourceData.tags ? osparc.store.Tags.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.getTagId())) : [];
      const card = this.getMode() === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      card.set({
        appearance: resourceData.type ? `pb-${resourceData.type.toLowerCase()}` : `pb-${resourceData.resourceType}`,
        resourceData: resourceData,
        tags
      });
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });
      card.setMenu(menu);
      if (resourceData.type !== "study") {
        // the backend will do the projects:search
        card.subscribeToFilterGroup("searchBarFilter");
      }

      [
        "updateStudy",
        "updateTemplate",
        "updateTutorial",
        "updateService",
        "updateHypertool",
        "publishTemplate",
        "tagClicked",
        "emptyStudyClicked"
      ].forEach(eName => card.addListener(eName, e => this.fireDataEvent(eName, e.getData())));
      return card;
    },

    __addCardToContainer: function(card, container) {
      if (container == null) {
        return;
      }

      container.add(card);

      if (this.getMode() === "list") {
        const fitToContainer = () => {
          const bounds = container.getBounds() || container.getSizeHint();
          card.setWidth(bounds.width);
        };
        [
          "appear",
          "resize",
        ].forEach(ev => {
          container.addListener(ev, () => fitToContainer());
        });
        fitToContainer();
      }
    },

    setResourcesToList: function(resourcesList) {
      this.__resourcesList = resourcesList;

      this.__evaluateNoResourcesFoundLabel();
    },

    __cleanAll: function() {
      if (this._getChildren().includes(this.__nonGroupedContainer)) {
        this._remove(this.__nonGroupedContainer);
      }
      if (this._getChildren().includes(this.__groupedContainers)) {
        this._remove(this.__groupedContainers);
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
    },

    __rebuildLayout: function(resourceType) {
      this.__cleanAll();
      if (this.getGroupBy()) {
        let groupTitle = "No Group";
        switch (this.getGroupBy()) {
          case "tags":
            groupTitle = "Not Tagged";
            break;
          case "shared":
            groupTitle = "Not Shared";
            break;
          case "groupedServices":
            groupTitle = "Misc";
            break;
        }
        const noGroupContainer = this.__createGroupContainer("no-group", groupTitle, "text");
        this.__groupedContainers.add(noGroupContainer);
        this._add(this.__groupedContainers);
      } else {
        const flatList = this.__nonGroupedContainer = this.__createFlatList();
        osparc.utils.Utils.setIdToWidget(flatList, resourceType + "List");
        this._add(flatList);
      }
    },

    __createFlatList: function() {
      const flatList = new osparc.dashboard.CardContainer();
      osparc.dashboard.ResourceContainerManager.updateSpacing(this.getMode(), flatList);
      this.addListener("changeMode", () => osparc.dashboard.ResourceContainerManager.updateSpacing(this.getMode(), flatList));
      [
        "changeSelection",
        "changeVisibility"
      ].forEach(signalName => {
        flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
      });
      return flatList;
    },

    __createGroupContainer: function(groupId, headerLabel, headerColor = "text") {
      const groupContainer = new osparc.dashboard.GroupedCardContainer().set({
        groupId: groupId.toString(),
        headerLabel,
        headerIcon: "",
        headerColor,
        visibility: "excluded"
      });

      this.bind("mode", groupContainer, "mode");
      [
        "changeSelection",
        "changeVisibility"
      ].forEach(signalName => {
        groupContainer.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
      });

      this.__groupedContainersList.push(groupContainer);
      return groupContainer;
    },

    reloadCards: function(resourceType) {
      this.__rebuildLayout(resourceType);

      const cards = [];
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
      if (this.__workspacesContainer) {
        this.__workspacesContainer.removeAll();
        this.__workspacesContainer.exclude();
      }
      let workspacesCards = [];
      this.__workspacesList.forEach(workspaceData => workspacesCards.push(this.__workspaceToCard(workspaceData)));
      return workspacesCards;
    },

    addNewWorkspaceCard: function(newWorkspaceCard) {
      this.__workspacesContainer.addAt(newWorkspaceCard, 0);
      this.__workspacesContainer.show();
    },

    __workspaceToCard: function(workspaceData) {
      const card = this.__createWorkspaceCard(workspaceData);
      this.__workspacesContainer.add(card);
      this.__workspacesContainer.show();
      return card;
    },

    __createWorkspaceCard: function(workspace) {
      const card = new osparc.dashboard.WorkspaceButtonItem(workspace);
      [
        "workspaceSelected",
        "workspaceUpdated",
        "trashWorkspaceRequested",
        "untrashWorkspaceRequested",
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
        this.__foldersContainer.exclude();
      }
      let folderCards = [];
      this.__foldersList.forEach(folderData => folderCards.push(this.__folderToCard(folderData)));
      return folderCards;
    },

    addNewFolderCard: function(newFolderCard) {
      this.__foldersContainer.addAt(newFolderCard, 0);
      this.__foldersContainer.show();
    },

    __folderToCard: function(folderData) {
      const card = this.__createFolderCard(folderData);
      this.__foldersContainer.add(card);
      this.__foldersContainer.show();
      return card;
    },

    __createFolderCard: function(folder) {
      const card = new osparc.dashboard.FolderButtonItem(folder);
      [
        "folderSelected",
        "folderUpdated",
        "moveFolderToRequested",
        "trashFolderRequested",
        "untrashFolderRequested",
        "deleteFolderRequested",
        "changeContext",
        "studyToFolderRequested",
        "folderToFolderRequested",
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
      const tags = resourceData.tags ? osparc.store.Tags.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.getTagId())) : [];
      if (tags.length === 0) {
        let noGroupContainer = this.__getGroupContainer("no-group");
        const card = this.__createCard(resourceData);
        this.__addCardToContainer(card, noGroupContainer);
        this.self().sortListByPriority(noGroupContainer.getContentContainer());
        cards.push(card);
      } else {
        tags.forEach(tag => {
          let groupContainer = this.__getGroupContainer(tag.getTagId());
          if (groupContainer === null) {
            groupContainer = this.__createGroupContainer(tag.getTagId(), tag.getName(), tag.getColor());
            tag.bind("name", groupContainer, "headerLabel");
            tag.bind("color", groupContainer, "headerColor");
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
            const groupsStore = osparc.store.Groups.getInstance();
            const group = groupsStore.getGroup(orgId);
            if (group) {
              let icon = "";
              if (group.getThumbnail()) {
                icon = group.getThumbnail();
              } else if (group["collabType"] === 0) {
                icon = "@FontAwesome5Solid/globe/24";
              } else if (group["collabType"] === 1) {
                icon = "@FontAwesome5Solid/users/24";
              } else if (group["collabType"] === 2) {
                icon = "@FontAwesome5Solid/user/24";
              }
              groupContainer.set({
                headerIcon: icon,
                headerLabel: group.getLabel(),
              });
            } else {
              groupContainer.exclude();
            }
            this.__groupedContainers.add(groupContainer);
            this.__moveNoGroupToLast();
          }
          const card = this.__createCard(resourceData);
          this.__addCardToContainer(card, groupContainer);
          this.self().sortListByPriority(groupContainer.getContentContainer());
          cards.push(card);
        });
      }
    },

    __groupByGroupedServices: function(cards, resourceData) {
      const groupedServicesConfig = osparc.store.Products.getInstance().getGroupedServicesUiConfig();
      if (groupedServicesConfig == null) {
        return;
      }

      // create group containers for each category
      groupedServicesConfig["categories"].forEach(category => {
        if (this.__getGroupContainer(category["id"]) === null) {
          const groupContainer = this.__createGroupContainer(category["id"], category["title"], category["color"]);
          groupContainer.setHeaderIcon("@FontAwesome5Solid/tag/24");
          this.__groupedContainers.add(groupContainer);
        }
      });

      // get the right container
      let container = null;
      const serviceKey = resourceData["key"];
      if (serviceKey) {
        const groupInfo = groupedServicesConfig["services"].find(serviceInfo => serviceInfo["serviceKey"] === serviceKey);
        if (groupInfo) {
          container = this.__getGroupContainer(groupInfo["category"]);
        }
      }
      if (container === null) {
        container = this.__getGroupContainer("no-group");
        container.setHeaderIcon("@FontAwesome5Solid/tag/24");
      }

      // create the card and add it to the container
      const card = this.__createCard(resourceData);
      this.__addCardToContainer(card, container);
      cards.push(card);

      this.__moveNoGroupToLast();
      this.__groupedContainersList.forEach(groupedContainer => {
        groupedContainer.setExpanded(true);
        groupedContainer.getExpandButton().exclude();
      });
    },

    __resourceToCards: function(resourceData) {
      const cardsCreated = [];
      if (this.getGroupBy() === "tags") {
        this.__groupByTags(cardsCreated, resourceData);
      } else if (this.getGroupBy() === "shared") {
        this.__groupByShareWith(cardsCreated, resourceData);
      } else if (this.getGroupBy() === "groupedServices") {
        this.__groupByGroupedServices(cardsCreated, resourceData);
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
