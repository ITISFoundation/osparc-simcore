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

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__resourcesList = [];

    const flatList = this.__flatList = new osparc.dashboard.ToggleButtonContainer();
    [
      "changeSelection",
      "changeVisibility"
    ].forEach(signalName => {
      flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
    });
    this._add(this.__flatList);

    this.__groupedContainers = [];
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
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data"
  },

  statics: {
    sortList: function(list) {
      list.getChildren().sort((a, b) => {
        let sortingValue = a.getPriority() - b.getPriority();
        if (sortingValue === 0 && a.isPropertyInitialized("lastChangeDate") && b.isPropertyInitialized("lastChangeDate")) {
          return b.get("lastChangeDate") - a.get("lastChangeDate");
        }
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
    __resourcesList: null,
    __flatList: null,
    __groupedContainers: null,

    addNonResourceCard: function(card) {
      if (card instanceof qx.ui.form.ToggleButton) {
        if (this.getGroupBy()) {
          // it will always go to the no-group group
          const noGroupContainer = this.__getGroupContainer("no-group");
          noGroupContainer.add(card);
          this.self().sortList(noGroupContainer.getContentContainer());
        } else {
          this.__flatList.add(card);
          this.self().sortList(this.__flatList);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    removeNonResourceCard: function(card) {
      if (card instanceof qx.ui.form.ToggleButton) {
        if (this.getGroupBy()) {
          const noGroupContainer = this.__getGroupContainer("no-group");
          noGroupContainer.getContentContainer().remove(card);
        } else {
          this.__flatList.remove(card);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    removeCard: function(uuid) {
      if (this.getGroupBy()) {
        this.__groupedContainers.forEach(groupedContainer => groupedContainer.removeCard(uuid));
      } else {
        this.__flatList.removeCard(uuid);
      }
    },

    getFlatList: function() {
      return this.__flatList;
    },

    __createGroupContainer: function(groupId, headerLabel, headerColor = "text") {
      const groupContainer = new osparc.dashboard.GroupedToggleButtonContainer().set({
        groupId: groupId.toString(),
        headerLabel,
        headerIcon: "",
        headerColor,
        visibility: "excluded"
      });
      this.__groupedContainers.push(groupContainer);
      return groupContainer;
    },

    __createEmptyGroupContainer: function() {
      const noGroupContainer = this.__createGroupContainer("no-group", this.tr("No Group"), "transparent");
      return noGroupContainer;
    },

    areMoreResourcesRequired: function(loadingResourcesBtn) {
      if (this.__flatList) {
        return this.__flatList.areMoreResourcesRequired(loadingResourcesBtn);
      }
      // If containers are grouped all the resources are expected to be fetched
      return false;
    },

    getCards: function() {
      if (this.__flatList) {
        return this.__flatList.getChildren();
      }
      const cards = [];
      this.__groupedContainers.forEach(groupedContainer => cards.push(...groupedContainer.getCards()));
      return cards;
    },

    getSelection: function() {
      if (this.getGroupBy() === null) {
        return this.__flatList.getSelection();
      }
      return [];
    },

    resetSelection: function() {
      if (this.getGroupBy() === null) {
        this.__flatList.resetSelection();
      }
    },

    __getGroupContainer: function(gid) {
      const idx = this.__groupedContainers.findIndex(groupContainer => groupContainer.getGroupId() === gid.toString());
      if (idx > -1) {
        return this.__groupedContainers[idx];
      }
      return null;
    },

    __createCard: function(resourceData, tags) {
      const card = this.getMode() === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      card.set({
        resourceData: resourceData,
        tags
      });
      if (this.getMode() === "list") {
        const width = this.getBounds().width - 15;
        card.setWidth(width);
      }
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });
      card.setMenu(menu);
      card.subscribeToFilterGroup("searchBarFilter");

      [
        "updateStudy",
        "updateTemplate",
        "updateService",
        "publishTemplate"
      ].forEach(ev => card.addListener(ev, e => this.fireDataEvent(ev, e.getData())));

      return card;
    },

    setResourcesToList: function(resourcesList) {
      this.__resourcesList = resourcesList;
    },

    __cleanAll: function() {
      if (this.__flatList) {
        this.__flatList.removeAll();
        this.__flatList = null;
      }
      this.__groupedContainers.forEach(groupedContainer => groupedContainer.getContentContainer().removeAll());
      this.__groupedContainers = [];
      this._removeAll();
    },

    reloadCards: function(listId) {
      this.__cleanAll();
      if (this.getGroupBy()) {
        const noGroupContainer = this.__createEmptyGroupContainer();
        this._add(noGroupContainer);
      } else {
        const flatList = this.__flatList = new osparc.dashboard.ToggleButtonContainer();
        osparc.utils.Utils.setIdToWidget(flatList, listId);
        [
          "changeSelection",
          "changeVisibility"
        ].forEach(signalName => {
          flatList.addListener(signalName, e => this.fireDataEvent(signalName, e.getData()), this);
        });
        const spacing = this.getMode() === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
        this.__flatList.getLayout().set({
          spacingX: spacing,
          spacingY: spacing
        });
        this._add(this.__flatList);
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

    __resourceToCards: function(resourceData) {
      const cards = [];
      const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];
      if (this.getGroupBy() === "tags") {
        if (tags.length === 0) {
          let noGroupContainer = this.__getGroupContainer("no-group");
          const card = this.__createCard(resourceData, tags);
          noGroupContainer.add(card);
          this.self().sortList(noGroupContainer.getContentContainer());
          cards.push(card);
        } else {
          tags.forEach(tag => {
            let groupContainer = this.__getGroupContainer(tag.id);
            if (groupContainer === null) {
              groupContainer = this.__createGroupContainer(tag.id, tag.name, tag.color);
              groupContainer.setHeaderIcon("@FontAwesome5Solid/tag/24");
              const idx = this._getChildren().findIndex(grpContainer => grpContainer === this.__getGroupContainer("no-group"));
              this._addAt(groupContainer, idx);
            }
            const card = this.__createCard(resourceData, tags);
            groupContainer.add(card);
            this.self().sortList(groupContainer.getContentContainer());
            cards.push(card);
          });
        }
      } else if (this.getGroupBy() === "shared") {
        let orgIds = [];
        if ("accessRights" in resourceData) {
          orgIds = Object.keys(resourceData["accessRights"]);
        }
        if (orgIds.length === 0) {
          let noGroupContainer = this.__getGroupContainer("no-group");
          const card = this.__createCard(resourceData, tags);
          noGroupContainer.add(card);
          this.self().sortList(noGroupContainer.getContentContainer());
          cards.push(card);
        } else {
          orgIds.forEach(orgId => {
            let groupContainer = this.__getGroupContainer(orgId);
            if (groupContainer === null) {
              groupContainer = this.__createGroupContainer(orgId, "loading-label");
              osparc.store.Store.getInstance().getOrganizationOrUser(orgId)
                .then(org => {
                  if (org) {
                    let icon = "";
                    if (org.thumbnail) {
                      icon = org.thumbnail;
                    } else if (org["collabType"] === 0) {
                      icon = "@FontAwesome5Solid/globe/24";
                    } else if (org["collabType"] === 1) {
                      icon = "@FontAwesome5Solid/users/24";
                    } else if (org["collabType"] === 2) {
                      icon = "@FontAwesome5Solid/user/24";
                    }
                    groupContainer.set({
                      headerIcon: icon,
                      headerLabel: org.label
                    });
                  } else {
                    // unknown org/user: show email address instead
                    groupContainer.set({
                      headerIcon: "@FontAwesome5Solid/user/24",
                      headerLabel: resourceData["prjOwner"]
                    });
                  }
                });
              const idx = this._getChildren().findIndex(grpContainer => grpContainer === this.__getGroupContainer("no-group"));
              this._addAt(groupContainer, idx);
            }
            const card = this.__createCard(resourceData, tags);
            groupContainer.add(card);
            this.self().sortList(groupContainer.getContentContainer());
            cards.push(card);
          });
        }
      } else {
        const card = this.__createCard(resourceData, tags);
        cards.push(card);
        this.__flatList.add(card);
        this.self().sortList(this.__flatList);
      }
      return cards;
    }
  }
});
