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

qx.Class.define("osparc.ui.table.cellrenderer.SVGButtonRenderer", {
  extend: osparc.ui.table.cellrenderer.Html,

  construct: function(id, icon) {
    this.base(arguments);
  },

  properties: {
    clickAction: {
      check: "String",
      nullable: false,
      init: "clickAction",
    },

    svgIcon: {
      check: "String",
      nullable: false,
      init: "osparc/offline.svg", // Default icon
    },
  },

  members: {
    // Override
    _getContentHtml: function(cellInfo) {
      const clickAction = this.getClickAction();
      const iconPath = this.getSvgIcon();
      const resMgr = qx.util.ResourceManager.getInstance();
      const iconUrl = resMgr.toUri(iconPath); // Resolves to the correct URL of the asset

      // Return the button with the image
      return `
        <div class="qx-material-button"
          data-action="${clickAction}" data-row="${cellInfo.row}"
          style="cursor:pointer; padding:2px 2px; width:29px; height:20px; display:flex; align-items:center; justify-content:center;"
        >
          <img src="${iconUrl}" style="width:16px; height:16px;" alt="icon"/>
        </div>
      `;
    },
  }
});
