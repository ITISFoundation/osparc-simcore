/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Dropdown menu for tag filtering
 */
qx.Class.define("osparc.filter.TagsFilter", {
  extend: osparc.filter.UIFilter,

  /**
   * Constructor for TagsFilter creates a TagsFilter.
   *
   * @extends osparc.filter.UIFilter
   */
  construct: function(label, filterId, filterGroupId) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.HBox());

    this.__dropdown = new qx.ui.toolbar.MenuButton(label).set({
      marginLeft: 0
    });
    this._add(this.__dropdown);

    this.__activeTags = [];
    this.__tagButtons = {};
  },

  properties: {
    printTags: {
      init: true,
      check: "Boolean",
      nullable: false
    }
  },

  statics: {
    ActiveTagIcon: "@FontAwesome5Solid/check/12"
  },

  members: {
    __dropdown: null,
    __activeTags: null,
    __tagButtons: null,
    __menu: null,

    /**
     * Implementing IFilter: Function in charge of resetting the filter.
     */
    reset: function() {
      // Remove ticks from menu
      const menuButtons = this._getMenuButtons();
      menuButtons.forEach(button => button.resetIcon());
      // Remove active tags
      if (this.__activeTags.length) {
        this.__activeTags.length = 0;
      }
      // Remove tag buttons
      for (let tagName in this.__tagButtons) {
        this._remove(this.__tagButtons[tagName]);
        delete this.__tagButtons[tagName];
      }
      this.__dispatch();
    },

    __dispatch: function() {
      this._filterChange(this.__activeTags);
    },

    getActiveTags: function() {
      return this.__activeTags;
    },

    _addTag: function(tagName, menuButton) {
      // Check if added
      if (this.__activeTags.includes(tagName)) {
        this.removeTag(tagName, menuButton);
      } else {
        // Save previous icon
        menuButton.prevIcon = menuButton.getIcon();
        // Add tick
        menuButton.setIcon(this.self().ActiveTagIcon);
        // Update state
        this.__activeTags.push(tagName);
        if (this.isPrintTags()) {
          // Add tag
          const tagButton = new qx.ui.toolbar.Button(tagName, "@MaterialIcons/close/12");
          this._add(tagButton);
          tagButton.addListener("execute", () => this.removeTag(tagName, menuButton));
          this.__tagButtons[tagName] = tagButton;
        }
      }
      this.__dispatch();
    },

    removeTag: function(tagName, menuButton) {
      if (menuButton === undefined) {
        menuButton = this._getMenuButtons().find(btn => btn.getLabel() === tagName);
      }
      // Restore icon
      menuButton.setIcon(menuButton.prevIcon);
      // Update state
      this.__activeTags.splice(this.__activeTags.indexOf(tagName), 1);
      if (tagName in this.__tagButtons) {
        this._remove(this.__tagButtons[tagName]);
        delete this.__tagButtons[tagName];
      }
      this.__dispatch();
    },

    _getMenuButtons: function() {
      const menu = this.__dropdown.getMenu();
      if (menu) {
        return menu.getChildren().filter(child => child instanceof qx.ui.menu.Button);
      }
      return [];
    },

    _getActiveMenuButtons: function() {
      const menuButtons = this._getMenuButtons();
      return menuButtons.filter(menuButton => menuButton.getIcon() === this.self().ActiveTagIcon);
    },

    _addOption: function(tagName) {
      if (this.__menu === null) {
        this.__menu = new qx.ui.menu.Menu();
        this.__dropdown.setMenu(this.__menu);
      }
      const existing = this.__menu.getChildren().find(button => button.getLabel && button.getLabel() === tagName);
      if (existing) {
        // Don't add repeated options
        return existing;
      }
      const button = new qx.ui.menu.Button(tagName);
      button.addListener("execute", e => this._addTag(tagName, e.getTarget()));
      this.__menu.add(button);
      return button;
    },

    _removeAllOptions: function() {
      if (this.__menu) {
        this.__menu.removeAll();
      }
    },

    _addSeparator: function() {
      if (this.__menu === null) {
        this.__menu = new qx.ui.menu.Menu();
        this.__dropdown.setMenu(this.__menu);
      }
      this.__menu.addSeparator();
    }
  }
});
