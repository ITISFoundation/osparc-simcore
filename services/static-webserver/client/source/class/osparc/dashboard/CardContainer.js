/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Container for GridButtons and ListButtons (CardBase, FolderButtonBase and WorkspaceButtonBase), with some convenient methods.
 */
qx.Class.define("osparc.dashboard.CardContainer", {
  extend: qx.ui.container.Composite,

  construct: function() {
    const spacing = osparc.dashboard.GridButtonBase.SPACING;
    const layout = new qx.ui.layout.Flow(spacing, spacing);
    this.base(arguments, layout);
  },

  events: {
    "changeSelection": "qx.event.type.Data",
    "changeVisibility": "qx.event.type.Data"
  },

  statics: {
    isValidCard: function(widget) {
      return (
        widget instanceof osparc.dashboard.CardBase ||
        widget instanceof osparc.dashboard.FolderButtonBase ||
        widget instanceof osparc.dashboard.WorkspaceButtonBase
      );
    },
  },

  members: {
    __lastSelectedIdx: null,

    // overridden
    add: function(child, options) {
      if (this.self().isValidCard(child)) {
        if (osparc.dashboard.ResourceContainerManager.cardExists(this, child)) {
          return;
        }
        this.base(arguments, child, options);
        child.addListener("changeSelected", () => this.fireDataEvent("changeSelection", this.getSelection()), this);
        child.addListener("changeVisibility", () => this.fireDataEvent("changeVisibility", this.__getVisibles()), this);
      } else {
        console.error("CardContainer only allows CardBase as its children.");
      }
    },

    /**
     * Resets the selection so no toggle button is checked.
     */
    resetSelection: function() {
      this.getChildren().map(button => button.setSelected(false));
      this.__lastSelectedIdx = null;
      this.fireDataEvent("changeSelection", this.getSelection());
    },

    /**
     * Returns an array that contains all buttons that are checked.
     */
    getSelection: function() {
      return this.getChildren().filter(button => button.getSelected());
    },

    /**
     * Returns an array that contains all visible buttons.
     */
    __getVisibles: function() {
      return this.getChildren().filter(button => button.isVisible());
    },

    /**
     * Sets the given button's select prop to true (checks it) and unchecks all other buttons. If the given button is not present,
     * every button in the container will get a unselected (unchecked).
     * @param {qx.ui.form.CardBase} child Button that will be checked
     */
    selectOne: function(child) {
      this.getChildren().map(button => button.setSelected(button === child));
      this.setLastSelectedIndex(this.getIndex(child));
    },

    /**
     * Gets the index in the container of the given button.
     * @param {qx.ui.form.CardBase} child Button that will be checked
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
      if (
        this.nextRequest !== null &&
        loadingResourcesBtn &&
        osparc.utils.Utils.isWidgetOnScreen(loadingResourcesBtn)
      ) {
        return true;
      }
      return false;
    },

    removeCard: function(key) {
      const cards = this.getChildren();
      for (let i=0; i<cards.length; i++) {
        const card = cards[i];
        if (card.isPropertyInitialized("uuid") && key === card.getUuid()) {
          this.remove(card);
        }
      }
    }
  }
});
