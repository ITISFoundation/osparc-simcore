/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Container for GridButtonItems and ListButtonItems (ToggleButtons), with some convenient methods.
 */
qx.Class.define("osparc.dashboard.ToggleButtonContainer", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments, new qx.ui.layout.Flow(15, 15));

    this.__emptyHeaders();
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
    __lastSelectedIdx: null,
    __groupHeaders: null,

    areMoreResourcesRequired: function(loadingResourcesBtn) {
      if (this.nextRequest !== null && loadingResourcesBtn &&
        (this.getVisibles().length < osparc.dashboard.ResourceBrowserBase.MIN_FILTERED_STUDIES ||
        osparc.utils.Utils.checkIsOnScreen(loadingResourcesBtn))
      ) {
        return true;
      }
      return false;
    },

    __reloadCards: function() {
      const cards = this.getCards();
      this.removeAll();
      const header = this.__emptyHeaders();
      if (this.getGroupBy()) {
        this.add(header);
      }
      cards.forEach(card => this.add(card));
    },

    __applyMode: function(mode) {
      const spacing = mode === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
      this.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
      this.__reloadCards();
    },

    __applyGroupBy: function() {
      this.__reloadCards();
    },

    getCards: function() {
      return this.getChildren().filter(child => !("GroupHeader" in child));
    },

    __configureCard: function(card) {
      card.addListener("changeValue", () => this.fireDataEvent("changeSelection", this.getSelection()), this);
      card.addListener("changeVisibility", () => this.fireDataEvent("changeVisibility", this.getVisibles()), this);
      if (this.getMode() === "list") {
        const width = this.getBounds().width - 15;
        card.setWidth(width);
      }
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

    /**
     * Resets the selection so no toggle button is checked.
     */
    resetSelection: function() {
      this.getCards().map(button => button.setValue(false));
      this.__lastSelectedIdx = null;
      this.fireDataEvent("changeSelection", this.getSelection());
    },

    /**
     * Returns an array that contains all buttons that are checked.
     */
    getSelection: function() {
      return this.getCards().filter(button => button.getValue());
    },

    /**
     * Returns an array that contains all visible buttons.
     */
    getVisibles: function() {
      return this.getCards().filter(button => button.isVisible());
    },

    /**
     * Gets the index in the container of the given button.
     * @param {qx.ui.form.ToggleButton} child Button that will be checked
     */
    getIndex: function(child) {
      return this.getCards().findIndex(button => button === child);
    },

    getLastSelectedIndex: function() {
      return this.__lastSelectedIdx;
    },

    setLastSelectedIndex: function(idx) {
      if (idx >= 0 && idx < this.getCards().length) {
        this.__lastSelectedIdx = idx;
      }
    }
  }
});
