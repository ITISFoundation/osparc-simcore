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
    id: {
      check: "String",
      nullable: false,
      init: "id",
    },

    fontIcon: {
      check: "String",
      nullable: false,
      init: "fas fa-info",
    },
  },

  members: {
    // Override
    _getContentHtml: function(cellInfo) {
      const id = this.getId();
      const icon = this.getFontIcon();
      return `
        <button class="action-btn" data-action="${id}" data-row="${cellInfo.row}" title="View">
          <i class="${icon}" style="font-size:12px; line-height:1;">></i>
        </button>
      `;
    }
  }
});
