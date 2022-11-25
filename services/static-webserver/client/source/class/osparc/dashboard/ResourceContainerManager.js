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

    __createHeader: function(label, color) {
      const header = new qx.ui.basic.Atom(label, "@FontAwesome5Solid/tag/24").set({
        gap: 10,
        padding: 10
      });
      header.getChildControl("icon").setTextColor(color);
      return header;
    },

    __createGroupContainer: function(groupId, header) {
      const groupContainer = new osparc.dashboard.GroupedToggleButtonContainer().set({
        groupId: groupId.toString(),
        visibility: "excluded"
      });
      groupContainer.setGroupHeader(header);
      this._add(groupContainer);
      this.__groupedContainers.push(groupContainer);
      return groupContainer;
    },

    __createEmptyGroupContainer: function() {
      const header = this.__createHeader(this.tr("No Group"), "transparent");
      const noGroupContainer = this.__createGroupContainer("no-group", header);
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
    },

    __createCard: function(resourceData, tags) {
      // create card
      const card = new osparc.dashboard.GridButtonItem();
      card.set({
        resourceData: resourceData,
        tags
      });
      card.subscribeToFilterGroup("searchBarFilter");
      return card;
    },

    setResourcesData: function(resourcesData) {
      this.__groupedContainers = [];
      if (this.getGroupBy() === "tags") {
        this.__createEmptyGroupContainer();
      } else {
        this.__flatList = new osparc.dashboard.ToggleButtonContainer();
        this._add(this.__flatList);
      }
      resourcesData.forEach(resourceData => {
        const tags = resourceData.tags ? osparc.store.Store.getInstance().getTags().filter(tag => resourceData.tags.includes(tag.id)) : [];
        if (this.getGroupBy() === "tags") {
          const card = this.__createCard(resourceData, tags);
          if (tags.length === 0) {
            let groupContainer = this.__getGroupContainer("no-group");
            groupContainer.add(card);
          } else {
            tags.forEach(tag => {
              let groupContainer = this.__getGroupContainer(tag.id);
              if (groupContainer === null) {
                const header = this.__createHeader(tag.name, tag.color);
                groupContainer = this.__createGroupContainer(tag.id, header);
              }
              groupContainer.add(card);
            });
          }
        } else {
          const card = this.__createCard(resourceData, tags);
          this.__flatList.add(card);
        }
      });
    }
  }
});
