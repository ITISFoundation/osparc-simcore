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

    this.__emptyHeaders();
    this.__groupedLists = [];
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
    __groupHeaders: null,
    __flatList: null,
    __groupedLists: null,

    __emptyHeaders: function() {
      const noGroupHeader = this.__createHeader(this.tr("No Group"), "transparent");
      this.__groupHeaders = {
        "no-group": {
          widget: noGroupHeader,
          children: []
        }
      };
      return noGroupHeader;
    },

    __createHeader: function(label, color) {
      const header = new osparc.dashboard.GroupHeader();
      header.set({
        minWidth: 1000,
        allowGrowX: true
      });
      header.buildLayout(label);
      header.getChildControl("icon").setBackgroundColor(color);
      return header;
    },

    // overridden
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
          this.base(arguments, child, options);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    __configureCard: function(card) {
      card.addListener("changeValue", () => this.fireDataEvent("changeSelection", this.getSelection()), this);
      card.addListener("changeVisibility", () => this.fireDataEvent("changeVisibility", this.__getVisibles()), this);
      if (this.getMode() === "list") {
        const width = this.getBounds().width - 15;
        card.setWidth(width);
      }
    },

    __addHeaders: function(child) {
      let headerInfo = null;
      if (this.getGroupBy() === "tags") {
        let tags = [];
        if (child.isPropertyInitialized("tags")) {
          tags = child.getTags();
        }
        if (tags.length === 0) {
          headerInfo = this.__groupHeaders["no-group"];
          headerInfo["children"].push(child);
        }
        tags.forEach(tag => {
          if (tag.id in this.__groupHeaders) {
            headerInfo = this.__groupHeaders[tag.id];
          } else {
            const header = this.__createHeader(tag.name, tag.color);
            headerInfo = {
              widget: header,
              children: []
            };
            this.__groupHeaders[tag.id] = headerInfo;
            this.add(header);
          }
          headerInfo["children"].push(child);
        });
      }
      return headerInfo;
    },

    __reloadCards: function() {
      const cards = this.getChildren();
      this.removeAll();
      const header = this.__emptyHeaders();
      if (this.getGroupBy()) {
        this.add(header);
      }
      cards.forEach(card => this.add(card));
    },

    areMoreResourcesRequired: function() {
      if (this.__flatList) {
        return this.__flatList.areMoreResourcesRequired();
      }
      return false;
    },

    getCards: function() {
      if (this.__flatList) {
        return this.__flatList.getCards();
      }
      const cards = [];
      this.__groupedLists.forEach(groupedList => cards.push(...groupedList.getCards()));
      return cards;
    },

    resetSelection: function() {
      if (this.__flatList) {
        this.__flatList.resetSelection();
      }
    },

    __applyGroupBy: function() {
      const cards = this.getCards();
      this.removeAll();
      const header = this.__emptyHeaders();
      if (this.getGroupBy()) {
        this.add(header);
      }
      cards.forEach(card => this.add(card));
    }
  }
});
