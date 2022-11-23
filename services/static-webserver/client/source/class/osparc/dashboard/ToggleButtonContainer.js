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
    if (layout === undefined) {
      const spacing = osparc.dashboard.GridButtonBase.SPACING;
      layout = new qx.ui.layout.Flow(spacing, spacing);
    }
    this.base(arguments, layout);
  },

  properties: {
    mode: {
      check: ["grid", "list"],
      init: "grid",
      nullable: false,
      event: "changeMode",
      apply: "__applyMode"
    }
  },

  events: {
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data"
  },

  members: {
    __lastSelectedIdx: null,

    // overridden
    add: function(child, options) {
      if (child instanceof qx.ui.form.ToggleButton) {
        this.base(arguments, child, options);
        child.addListener("changeValue", () => this.fireDataEvent("changeSelection", this.getSelection()), this);
        child.addListener("changeVisibility", () => this.fireDataEvent("changeVisibility", this.__getVisibles()), this);
        if (this.getMode() === "list") {
          const width = this.getBounds().width - 15;
          child.setWidth(width);
        }
      } else {
        console.error("ToggleButtonContainer only allows ToggleButton as its children.");
      }
    },

    /**
     * Resets the selection so no toggle button is checked.
     */
    resetSelection: function() {
      this.getChildren().map(button => button.setValue(false));
      this.__lastSelectedIdx = null;
      this.fireDataEvent("changeSelection", this.getSelection());
    },

    /**
     * Returns an array that contains all buttons that are checked.
     */
    getSelection: function() {
      return this.getChildren().filter(button => button.getValue());
    },

    /**
     * Returns an array that contains all visible buttons.
     */
    __getVisibles: function() {
      return this.getChildren().filter(button => button.isVisible());
    },

    /**
     * Sets the given button's value to true (checks it) and unchecks all other buttons. If the given button is not present,
     * every button in the container will get a false value (unchecked).
     * @param {qx.ui.form.ToggleButton} child Button that will be checked
     */
    selectOne: function(child) {
      this.getChildren().map(button => button.setValue(button === child));
      this.setLastSelectedIndex(this.getIndex(child));
    },

    /**
     * Gets the index in the container of the given button.
     * @param {qx.ui.form.ToggleButton} child Button that will be checked
     */
    getIndex: function(child) {
      return this.getChildren().findIndex(button => button === child);
    },

    getLastSelectedIndex: function() {
      return this.__lastSelectedIdx;
    },

    setLastSelectedIndex: function(idx) {
      if (idx >= 0 && idx < this.getChildren().length) {
        this.__lastSelectedIdx = idx;
      }
    },

    setLastSelectedItem: function(item) {
      this.setLastSelectedIndex(this.getIndex(item));
    },

    areMoreResourcesRequired: function(loadingResourcesBtn) {
      if (this.nextRequest !== null && loadingResourcesBtn &&
        (this.__getVisibles().length < osparc.dashboard.ResourceBrowserBase.MIN_FILTERED_STUDIES ||
        osparc.utils.Utils.checkIsOnScreen(loadingResourcesBtn))
      ) {
        return true;
      }
      return false;
    },

    __applyMode: function(mode) {
      const spacing = mode === "grid" ? osparc.dashboard.GridButtonBase.SPACING : osparc.dashboard.ListButtonBase.SPACING;
      this.getLayout().set({
        spacingX: spacing,
        spacingY: spacing
      });
    },

    removeCard: function(key) {
      const cards = this.getChildren();
      for (let i=0; i<cards.length; i++) {
        const card = cards[i];
        if (card.getUuid && key === card.getUuid()) {
          this.remove(card);
          return;
        }
      }
    }
  }
});
