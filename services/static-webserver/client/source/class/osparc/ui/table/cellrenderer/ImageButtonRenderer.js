/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2035 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.table.cellrenderer.ImageButtonRenderer", {
  extend: osparc.ui.table.cellrenderer.ButtonRenderer,

  construct: function(clickAction, icon) {
    this.base(arguments);
  },

  properties: {
    iconPath: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__applyIconPath",
    },
  },

  members: {
    __applyIconPath: function(iconPath) {
      const resMgr = qx.util.ResourceManager.getInstance();
      const iconUrl = resMgr.toUri(iconPath); // Resolves to the correct URL of the asset

      this.setButtonContent(`<img src="${iconUrl}" style="width:14x; height:14px;" alt="icon"/>`);
    },
  }
});
