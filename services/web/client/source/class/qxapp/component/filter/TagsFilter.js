/* ************************************************************************

   qxapp - the simcore frontend

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

qx.Class.define("qxapp.component.filter.TagsFilter", {
  extend: qxapp.component.filter.UIFilter,

  construct: function(filterId, groupId, labelTr = "Tags") {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.HBox());

    const dropDown = new qx.ui.toolbar.MenuButton(this.tr(labelTr));
    dropDown.setMenu(this.__buildMenu());
    this._add(dropDown);
  },

  members: {
    __activeTags: null,
    __tagButtons: null,

    __buildMenu: function() {
      const menu = new qx.ui.menu.Menu();

      this.__getServiceTypes().forEach(serviceType => {
        const button = new qx.ui.menu.Button(qxapp.utils.Utils.capitalize(serviceType));
        button.addListener("tap", e => this.__addTag(serviceType, e.getTarget()));
        menu.add(button);
      });

      menu.addSeparator();

      this.__getServiceCategories().forEach(serviceCategory => {
        const button = new qx.ui.menu.Button(qxapp.utils.Utils.capitalize(serviceCategory));
        button.addListener("tap", e => this.__addTag(serviceCategory, e.getTarget()));
        menu.add(button);
      });
      return menu;
    },

    __getServiceTypes: function() {
      return [
        "computational",
        "dynamic"
      ];
    },

    __getServiceCategories: function() {
      return [
        "data",
        "modeling",
        "simulator",
        "solver",
        "postpro",
        "notebook"
      ];
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
        const tagButton = new qx.ui.toolbar.Button(qxapp.utils.Utils.capitalize(tagName), "@MaterialIcons/close/12");
        this._add(tagButton);
        tagButton.addListener("tap", () => this.__removeTag(tagName, menuButton));
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
