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
qx.Class.define("osparc.component.filter.TagsFilter", {
  extend: osparc.component.filter.UIFilter,

  /**
   * Constructor for TagsFilter creates a TagsFilter.
   *
   * @extends osparc.component.filter.UIFilter
   */
  construct: function(label, filterId, groupId) {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.HBox());

    this._dropdown = new qx.ui.toolbar.MenuButton(label);
    this._add(this._dropdown);
  },

  members: {
    _dropdown: null,
    __activeTags: null,
    __tagButtons: null,
    __menu: null,

    /**
     * Implementing IFilter: Function in charge of resetting the filter.
     */
    reset: function() {
      // Remove ticks from menu
      const menuButtons = this._dropdown.getMenu().getChildren()
        .filter(child => child instanceof qx.ui.menu.Button);
      menuButtons.forEach(button => button.resetIcon());
      // Remove active tags
      if (this.__activeTags && this.__activeTags.length) {
        this.__activeTags.length = 0;
      }
      // Remove tag buttons
      for (let tagName in this.__tagButtons) {
        this._remove(this.__tagButtons[tagName]);
        delete this.__tagButtons[tagName];
      }
      // Dispatch
      this._filterChange(this.__activeTags);
    },

    __addTag: function(tagName, menuButton) {
      // Check if added
      this.__activeTags = this.__activeTags || [];
      if (this.__activeTags.includes(tagName)) {
        this.__removeTag(tagName, menuButton);
      } else {
        // Save previous icon
        menuButton.prevIcon = menuButton.getIcon();
        // Add tick
        menuButton.setIcon("@FontAwesome5Solid/check/12");
        // Add tag
        const tagButton = new qx.ui.toolbar.Button(tagName, "@MaterialIcons/close/12");
        this._add(tagButton);
        tagButton.addListener("execute", () => this.__removeTag(tagName, menuButton));
        // Update state
        this.__activeTags.push(tagName);
        this.__tagButtons = this.__tagButtons || {};
        this.__tagButtons[tagName] = tagButton;
      }
      // Dispatch
      this._filterChange(this.__activeTags);
    },

    __removeTag: function(tagName, menuButton) {
      // Restore icon
      menuButton.setIcon(menuButton.prevIcon);
      // Update state
      this.__activeTags.splice(this.__activeTags.indexOf(tagName), 1);
      this._remove(this.__tagButtons[tagName]);
      delete this.__tagButtons[tagName];
      // Dispatch
      this._filterChange(this.__activeTags);
    },

    _addOption: function(tagName) {
      if (this.__menu === null) {
        this.__menu = new qx.ui.menu.Menu();
        this._dropdown.setMenu(this.__menu);
      }
      if (this.__menu.getChildren().find(button => button.getLabel && button.getLabel() === tagName)) {
        // Don't add repeated options
        return;
      }
      const button = new qx.ui.menu.Button(tagName);
      button.addListener("execute", e => this.__addTag(tagName, e.getTarget()));
      this.__menu.add(button);
      return button;
    },

    _addSeparator: function() {
      if (this.__menu === null) {
        this.__menu = new qx.ui.menu.Menu();
        this._dropdown.setMenu(this.__menu);
      }
      this.__menu.addSeparator();
    }
  }
});
