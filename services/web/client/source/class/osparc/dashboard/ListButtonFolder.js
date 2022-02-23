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
  include: osparc.dashboard.MButtonFolder,

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
    __applyId: function(value) {
      const folders = osparc.store.Store.getInstance().getFolders();
      const foundFolder = folders.find(folder => folder.id === value);
      if (foundFolder) {
        this.setTitle(foundFolder.name);

        const description = this.getChildControl("description");
        description.setValue(foundFolder.description);

        const icon = this.getChildControl("icon").getChildControl("image");
        icon.setTextColor(foundFolder.color);
      }
    },

    // overridden
    _applyLastChangeDate: function(value, old) {
      if (value) {
        const label = this.getChildControl("last-change");
        label.setValue(osparc.utils.Utils.formatDateAndTime(value));
      }
    }
  }
});
