/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ListButtonFolder", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  properties: {
    id: {
      check: "Number",
      nullable: false,
      init: null,
      apply: "__applyId"
    }
  },

  members: {
    __buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Folder"));

      this.setIcon(osparc.dashboard.CardBase.FOLDER_ICON);
    },

    __applyId: function(value) {
      const tags = osparc.store.Store.getInstance().getTags();
      const foundTag = tags.find(tag => tag.id === value);
      if (foundTag) {
        const title = this.getChildControl("title");
        title.setValue(foundTag.name);

        const description = this.getChildControl("description");
        description.setValue(foundTag.description);

        const icon = this.getChildControl("icon").getChildControl("image");
        icon.setTextColor(foundTag.color);
      }
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      return false;
    },

    _shouldReactToFilter: function(data) {
      return false;
    }
  }
});
