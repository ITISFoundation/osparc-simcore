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

qx.Class.define("osparc.ui.table.cellrenderer.FontButtonRenderer", {
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

    fontIcon: {
      check: "String",
      nullable: false,
      // init: "@FontAwesome5Solid/eye/14",
      init: "fa-solid fa-eye",
    },
  },

  members: {
    // Override
    _getContentHtml: function(cellInfo) {
      const clickAction = this.getClickAction();
      const icon = this.getFontIcon();

      // const resMgr = qx.util.ResourceManager.getInstance();
      // const iconUri = resMgr.toUri(icon);
      // <img src="${iconUri}" style="${iconStyle}" />

      const iconStyle = "font-size:14px;";
      return `
        <button data-action="${clickAction}" data-row="${cellInfo.row}" title="View">
          <span class="${icon}" style="${iconStyle}"></span>
        </button>
      `;
    }
  }
});
