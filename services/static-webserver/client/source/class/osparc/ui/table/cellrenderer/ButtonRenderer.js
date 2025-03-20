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

qx.Class.define("osparc.ui.table.cellrenderer.ButtonRenderer", {
  extend: osparc.ui.table.cellrenderer.Html,

  construct: function(clickAction, icon) {
    this.base(arguments);
  },

  properties: {
    clickAction: {
      check: "String",
      nullable: false,
      init: "clickAction",
    },

    buttonContent: {
      check: "String",
      nullable: false,
      init: "",
    }
  },

  members: {
    // Override
    _getContentHtml: function(cellInfo) {
      const clickAction = this.getClickAction();
      const buttonContent = this.getButtonContent();

      // Return the button with the image
      return `
        <div class="qx-material-button"
          data-action="${clickAction}" data-row="${cellInfo.row}"
          style="cursor:pointer; padding:2px 2px; width:26px; height:18px; display:flex; align-items:center; justify-content:center;"
        >
          ${buttonContent}
        </div>
      `;
    },
  }
});
