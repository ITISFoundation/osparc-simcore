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
  include: osparc.dashboard.MButtonFolder,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  statics: {
    ICON_SIZE: 80
  },

  members: {
    __applyId: function(value) {
      const folders = osparc.store.Store.getInstance().getFolders();
      const foundFolder = folders.find(folder => folder.id === value);
      if (foundFolder) {
        this.setTitle(foundFolder.name);

        const description = this.getChildControl("subtitle-text");
        description.setValue(foundFolder.description);

        const icon = this.getChildControl("icon").getChildControl("image");
        icon.setTextColor(foundFolder.color);
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

    // overridden
    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("subtitle-text");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    }
  }
});
