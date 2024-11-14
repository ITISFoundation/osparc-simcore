/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Using the generic TagsFilter (name conflict) to filter by user-defined tags.
 */
qx.Class.define("osparc.filter.UserTagsFilter", {
  extend: osparc.filter.TagsFilter,
  construct: function(filterId, filterGroupId) {
    this.base(arguments, this.tr("Tags"), filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.HBox());
    this.__buildMenu();
    this.__attachEventListeners(filterId, filterGroupId);
  },
  members: {
    __buildMenu: function() {
      osparc.store.Tags.getInstance().getTags()
        .forEach(tag => {
          const menuButton = this._addOption(tag.getName());
          menuButton.setIcon("@FontAwesome5Solid/square/12");
          menuButton.getChildControl("icon").setTextColor(tag.getColor());
        });
    },
    __attachEventListeners: function(filterId, filterGroupId) {
      osparc.store.Store.getInstance().addListener("changeTags", () => {
        this._removeAllOptions();
        this.__buildMenu();
      }, this);
      qx.event.message.Bus.subscribe(osparc.utils.Utils.capitalize(filterGroupId, filterId, "trigger"), msg => {
        const menuButtons = this._getMenuButtons();
        const tagButton = menuButtons.find(btn => btn.getLabel() === msg.getData());
        this._addTag(tagButton.getLabel(), tagButton);
      }, this);
    }
  }
});
