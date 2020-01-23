/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Using the generic TagsFilter (name conflict) to filter by user-defined tags.
 */
qx.Class.define("osparc.component.filter.UserTagsFilter", {
  extend: osparc.component.filter.TagsFilter,
  construct: function(filterId, groupId) {
    this.base(arguments, this.tr("Tags"), filterId, groupId);
    this._setLayout(new qx.ui.layout.HBox());
    this.__buildMenu();
  },
  members: {
    __buildMenu: function() {
      osparc.data.Resources.get("tags")
        .then(tags => {
          tags.forEach(tag => {
            const menuButton = this._addOption(tag.name);
            menuButton.setIcon("@FontAwesome5Solid/square/12")
            menuButton.getChildControl("icon").setTextColor(tag.color);
          });
        });
    }
  }
})