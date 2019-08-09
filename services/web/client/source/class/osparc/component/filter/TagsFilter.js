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
   * Constructor for TagsFilter creates a workbench TagsFilter.
   *
   * @extends osparc.component.filter.UIFilter
   */
  construct: function(filterId, groupId) {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.HBox());

    this.__dropDown = new qx.ui.toolbar.MenuButton(this.tr("Tags"));
    this.__dropDown.setMenu(this.__buildMenu());
    this._add(this.__dropDown);
  },

  members: {
    __dropDown: null,
    __activeTags: null,
    __tagButtons: null,

    /**
     * Implementing IFilter: Function in charge of resetting the filter.
     */
    reset: function() {
      // Remove ticks from menu
      const menuButtons = this.__dropDown.getMenu().getChildren()
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

    __buildMenu: function() {
      const menu = new qx.ui.menu.Menu();

      osparc.utils.Services.getTypes().forEach(serviceType => {
        const button = new qx.ui.menu.Button(osparc.utils.Utils.capitalize(serviceType));
        button.addListener("execute", e => this.__addTag(serviceType, e.getTarget()));
        menu.add(button);
      });

      menu.addSeparator();

      osparc.utils.Services.getCategories().forEach(serviceCategory => {
        const button = new qx.ui.menu.Button(osparc.utils.Utils.capitalize(serviceCategory));
        button.addListener("execute", e => this.__addTag(serviceCategory, e.getTarget()));
        menu.add(button);
      });
      return menu;
    },

    __addTag: function(tagName, menuButton) {
      // Check if added
      this.__activeTags = this.__activeTags || [];
      if (this.__activeTags.includes(tagName)) {
        this.__removeTag(tagName, menuButton);
      } else {
        // Add tick
        menuButton.setIcon("@FontAwesome5Solid/check/12");
        // Add tag
        const tagButton = new qx.ui.toolbar.Button(osparc.utils.Utils.capitalize(tagName), "@MaterialIcons/close/12");
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
      // Remove tick
      menuButton.resetIcon();
      // Update state
      this.__activeTags.splice(this.__activeTags.indexOf(tagName), 1);
      this._remove(this.__tagButtons[tagName]);
      delete this.__tagButtons[tagName];
      // Dispatch
      this._filterChange(this.__activeTags);
    }
  }
});
