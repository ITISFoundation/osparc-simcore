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

    this.__flatList = new osparc.dashboard.ToggleButtonContainer();
    this._add(this.__flatList);

    this.__groupedContainers = [];
  },

  properties: {
    mode: {
      check: ["grid", "list"],
      init: "grid",
      nullable: false,
      event: "changeMode",
      apply: "__applyMode"
    },

    groupBy: {
      check: [null, "tags"],
      init: null,
      nullable: true,
      apply: "__applyGroupBy"
    }
  },

  events: {
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data"
  },

  members: {
    __flatList: null,
    __groupedContainers: null,

    add: function(child, options) {
      if (child instanceof qx.ui.form.ToggleButton) {
        if (this.getGroupBy()) {
          const headerInfo = this.__addHeaders(child);
          const headerIdx = this.getChildren().findIndex(button => button === headerInfo.widget);
          const childIdx = headerInfo["children"].findIndex(button => button === child);
          this.addAt(child, headerIdx+1+childIdx);
        } else {
          this.__flatList.add(child, options);
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
        return false;
        // FIXME OM
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

    __applyMode: function(mode) {
      if (this.getGroupBy() === null) {
        this.__flatList.setMode(mode);
      }
    },

    __getGroupContainer: function(gid) {
      const idx = this.__groupedContainers.findIndex(groupContainer => groupContainer.getGroupId() === gid.toString());
      if (idx > -1) {
        return this.__groupedContainers[idx];
      }
      return null;
    },

    __applyGroupBy: function() {
      this._removeAll();
      this.__groupedContainers = [];
      if (this.getGroupBy() === "tags") {
        const noGroupContainer = this.__createEmptyGroupContainer();
        this._add(noGroupContainer);
      } else {
        this.__flatList = new osparc.dashboard.ToggleButtonContainer();
        this._add(this.__flatList);
      }
    },

    __createCard: function(resourceData, tags) {
      const card = this.getMode() === "grid" ? new osparc.dashboard.GridButtonItem() : new osparc.dashboard.ListButtonItem();
      card.set({
        resourceData: resourceData,
        tags
      });
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });
      card.setMenu(menu);
      card.subscribeToFilterGroup("searchBarFilter");
      return card;
    },

    setResourcesData: function(resourcesData) {
      let cards = [];
      resourcesData.forEach(resourceData => {
        const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];
        if (this.getGroupBy() === "tags") {
          const card = this.__createCard(resourceData, tags);
          cards.push(card);
          if (tags.length === 0) {
            let noGroupContainer = this.__getGroupContainer("no-group");
            noGroupContainer.add(card);
          } else {
            tags.forEach(tag => {
              let groupContainer = this.__getGroupContainer(tag.id);
              if (groupContainer === null) {
                groupContainer = this.__createGroupContainer(tag.id, tag.name, tag.color);
                // Add it right before the no-group
                const noGroupContainer = this.__getGroupContainer("no-group");
                const idx = this._getChildren().findIndex(grpContainer => grpContainer === noGroupContainer);
                this._addAt(groupContainer, idx);
              }
              groupContainer.add(card);
            });
          }
        } else {
          const card = this.__createCard(resourceData, tags);
          cards.push(card);
          this.__flatList.add(card);
        }
      });
      return cards;
    }
  }
});
