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
      init: "fa-cog",
    },
  },

  members: {
    // Override
    _getContentHtml: function(cellInfo) {
      const clickAction = this.getClickAction();
      const iconClass = this.getFontIcon();

      const buttonStyle = "background:none; border:none; padding:0; cursor:pointer; height:32px; width:32px; display:flex; align-items:center; justify-content:center;";
      const iconStyle = "font-size:20px; width:24px; height:24px; display:flex; align-items:center; justify-content:center;";
      return `
        <button style="${buttonStyle}" data-action="${clickAction}" data-row="${cellInfo.row}" title="View">
          <span class="fa ${iconClass}" style="${iconStyle}"></span>
        </button>
      `;
    }
  }
});
