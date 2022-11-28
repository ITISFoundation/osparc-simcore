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
      check: [null, "tags"],
      init: null,
      nullable: true
    }
  },

  events: {
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data"
  },

  members: {
    __flatList: null,
    __groupedContainers: null,
    __resourcesList: null,

    add: function(child, options) {
      if (child instanceof qx.ui.form.ToggleButton) {
        if (this.getGroupBy()) {
          const headerInfo = this.__addHeaders(child);
          const headerIdx = this.getChildren().findIndex(button => button === headerInfo.widget);
          const childIdx = headerInfo["children"].findIndex(button => button === child);
          this.addAt(child, headerIdx+1+childIdx);
        } else {
          this.__flatList.add(child, options);
          this.__flatList.getChildren().sort((a, b) => a.getPriority() - b.getPriority());
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    getFlatList: function() {
      return this.__flatList;
    },

    __createGroupContainer: function(groupId, headerLabel, headerColor) {
      const groupContainer = new osparc.dashboard.GroupedToggleButtonContainer().set({
        groupId: groupId.toString(),
        headerLabel,
        headerIcon: "@FontAwesome5Solid/tag/24",
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

    resetSelection: function() {
      if (this.getGroupBy() === null) {
        this.__flatList.resetSelection();
      }
    },

    removeCard: function(key) {
      if (this.getGroupBy()) {
        this.__groupedContainers.forEach(groupedContainer => groupedContainer.removeCard(key));
      } else {
        this.__flatList.removeCard(key);
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
      return card;
    },

    setResourcesToList: function(resourcesList) {
      this.__resourcesList = resourcesList;
    },

    __cleanAll: function() {
      if (this.__flatList) {
        this.__flatList.removeAll();
      }
      this.__groupedContainers.forEach(groupedContainer => groupedContainer.getChildControl("content-container").removeAll());
      this.__groupedContainers = [];
      this._removeAll();
    },

    reloadCards: function() {
      this.__cleanAll();
      if (this.getGroupBy() === "tags") {
        const noGroupContainer = this.__createEmptyGroupContainer();
        this._add(noGroupContainer);
      } else {
        const flatList = this.__flatList = new osparc.dashboard.ToggleButtonContainer();
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
        Array.prototype.push.apply(cards, this.__reourceToCards(resourceData));
      });
      return cards;
    },

    reloadNewCards: function() {
      let newCards = [];
      const currentCards = this.getCards();
      this.__resourcesList.forEach(resourceData => {
        const idx = currentCards.findIndex(card => card.isPropertyInitialized("uuid") && resourceData["uuid"] === card.getUuid());
        if (idx === -1) {
          Array.prototype.push.apply(newCards, this.__reourceToCards(resourceData));
        }
      });
      return newCards;
    },

    __reourceToCards: function(resourceData) {
      const cards = [];
      const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];
      if (this.getGroupBy() === "tags") {
        if (tags.length === 0) {
          let noGroupContainer = this.__getGroupContainer("no-group");
          const card = this.__createCard(resourceData, tags);
          noGroupContainer.add(card);
          cards.push(card);
        } else {
          tags.forEach(tag => {
            let groupContainer = this.__getGroupContainer(tag.id);
            if (groupContainer === null) {
              groupContainer = this.__createGroupContainer(tag.id, tag.name, tag.color);
              const noGroupContainer = this.__getGroupContainer("no-group");
              const idx = this._getChildren().findIndex(grpContainer => grpContainer === noGroupContainer);
              this._addAt(groupContainer, idx);
            }
            const card = this.__createCard(resourceData, tags);
            groupContainer.add(card);
            cards.push(card);
          });
        }
      } else {
        const card = this.__createCard(resourceData, tags);
        cards.push(card);
        this.__flatList.add(card);
        this.__flatList.getChildren().sort((a, b) => a.getPriority() - b.getPriority());
      }
      return cards;
    }
  }
});
