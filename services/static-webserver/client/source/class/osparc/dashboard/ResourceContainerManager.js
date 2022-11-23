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
    this.base(arguments, new qx.ui.layout.VBox(10));

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
        if ("GroupHeader" in child) {
          this.base(arguments, child);
          return;
        }
        this.__configureCard(child);
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

    __createHeader: function(label, color) {
      const header = new qx.ui.basic.Atom(label, "@FontAwesome5Solid/tag/12");
      header.getChildControl("icon").setBackgroundColor(color);
      return header;
    },

    __createGroupContainer: function(groupId, header) {
      const groupContainer = new osparc.dashboard.GroupedToggleButtonContainer().set({
        groupId: groupId
      });
      groupContainer.setGroupHeader(header);
      return groupContainer;
    },

    __createEmptyGroupContainer: function() {
      const header = this.__createHeader(this.tr("No Group"), "transparent");
      const noGroupContainer = this.__createGroupContainer("no-group", header);
      return noGroupContainer;
    },

    __configureCard: function(card) {
      card.addListener("changeValue", () => this.fireDataEvent("changeSelection", this.getSelection()), this);
      card.addListener("changeVisibility", () => this.fireDataEvent("changeVisibility", this.__getVisibles()), this);
      if (this.getMode() === "list") {
        const width = this.getBounds().width - 15;
        card.setWidth(width);
      }
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
        return this.__flatList.getCards();
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
      const idx = this.__groupedContainers.findIndex(groupContainer => groupContainer.getGroupId() === gid);
      if (idx > -1) {
        return this.__groupedContainers[idx];
      }
      return null;
    },

    __populateGroups: function(cards) {
      this.__groupedContainers = [];
      const emptyGroupContainer = this.__createEmptyGroupContainer();
      this.__groupedContainers.push(emptyGroupContainer);
      this._add(emptyGroupContainer);

      cards.forEach(card => {
        if (this.getGroupBy() === "tags") {
          let tags = [];
          if (card.isPropertyInitialized("tags")) {
            tags = card.getTags();
          }
          if (tags.length === 0) {
            tags.push({
              id: "no-group",
              label: this.tr("No group"),
              color: "transparent"
            });
          }
          tags.forEach(tag => {
            let groupContainer = this.__getGroupContainer(tag.id);
            if (groupContainer === null) {
              const header = this.__createHeader(this.tr(tag.name), tag.color);
              groupContainer = this.__createGroupContainer(tag.id, header);
              this.__groupedContainers.push(groupContainer);
            }
            groupContainer.add(card);
          });
        }
      });
    },

    __applyGroupBy: function() {
      const cards = this.getCards();
      this.removeAll();
      if (this.getGroupBy()) {
        this.__populateGroups(cards);
      } else {
        this.__flatList = new osparc.dashboard.ToggleButtonContainer();
        cards.forEach(card => this.__flatList.add(card));
        this._add(this.__flatList);
      }
    }
  }
});
