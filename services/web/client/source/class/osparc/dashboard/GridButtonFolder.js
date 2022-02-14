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

qx.Class.define("osparc.dashboard.GridButtonFolder", {
  extend: osparc.dashboard.GridButtonBase,

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

  statics: {
    ICON_SIZE: 80
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

        const description = this.getChildControl("subtitle-text");
        description.setValue(foundTag.description);

        const icon = this.getChildControl("icon").getChildControl("image");
        icon.setTextColor(foundTag.color);
      }
    },

    // overridden
    _applyIcon: function(value) {
      this.base(arguments, value);

      const image = this.getChildControl("icon").getChildControl("image");
      let imgSrc = image.getSource();
      imgSrc = imgSrc.replace("/"+osparc.dashboard.GridButtonBase.ICON_SIZE, "/"+this.self().ICON_SIZE);
      image.setSource(imgSrc);
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
