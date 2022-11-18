/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Container for GridButtonItems and ListButtonItems (ToggleButtons), with some convenient methods.
 */
qx.Class.define("osparc.dashboard.ToggleButtonContainer", {
  extend: qx.ui.container.Composite,

  construct: function(layout) {
    this.base(arguments, layout);

    this.__groupMap = [];
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
      check: [null, "tag"],
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
    __groupMap: null,

    __reloadCards: function() {
      const cards = this.__getCards();
      this.removeAll();
      this.__groupMap = [];
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

    __getCards: function() {
      return this.getChildren().filter(child => !("GroupHeader" in child));
    },

    // overridden
    add: function(child, options) {
      if (child instanceof qx.ui.form.ToggleButton) {
        if ("GroupHeader" in child) {
          this.base(arguments, child, options);
          return;
        }
        if (this.getGroupBy()) {
          this.__addHeaders(child);
        }
        this.base(arguments, child, options);
        child.addListener("changeValue", () => this.fireDataEvent("changeSelection", this.getSelection()), this);
        child.addListener("changeVisibility", () => this.fireDataEvent("changeVisibility", this.getVisibles()), this);
        if (this.getMode() === "list") {
          const width = this.getBounds().width - 15;
          child.setWidth(width);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    __addHeaders: function(child) {
      if (this.getGroupBy() === "tag" && child.isPropertyInitialized("tags")) {
        child.getTags().forEach(tag => {
          if (!(this.__groupMap.includes(tag.id))) {
            const header = new osparc.dashboard.GroupHeader();
            header.set({
              width: this.getBounds().width - 15
            });
            header.buildLayout(tag.name);
            header.getChildControl("icon").setBackgroundColor(tag.color);
            this.__groupMap.push(tag.id);
            this.add(header);
          }
        });
      }
    },

    /**
     * Resets the selection so no toggle button is checked.
     */
    resetSelection: function() {
      this.__getCards().map(button => button.setValue(false));
      this.__lastSelectedIdx = null;
      this.fireDataEvent("changeSelection", this.getSelection());
    },

    /**
     * Returns an array that contains all buttons that are checked.
     */
    getSelection: function() {
      return this.__getCards().filter(button => button.getValue());
    },

    /**
     * Returns an array that contains all visible buttons.
     */
    getVisibles: function() {
      return this.__getCards().filter(button => button.isVisible());
    },

    /**
     * Gets the index in the container of the given button.
     * @param {qx.ui.form.ToggleButton} child Button that will be checked
     */
    getIndex: function(child) {
      return this.__getCards().findIndex(button => button === child);
    },

    getLastSelectedIndex: function() {
      return this.__lastSelectedIdx;
    },

    setLastSelectedIndex: function(idx) {
      if (idx >= 0 && idx < this.__getCards().length) {
        this.__lastSelectedIdx = idx;
      }
    }
  }
});
