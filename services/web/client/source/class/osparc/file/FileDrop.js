/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.file.FileDrop", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.setDroppable(true);

    this.getContentElement().setStyles({
      "border-radius": "20px",
      "border-color": qx.theme.manager.Color.getInstance().resolve("background-main-lighter+"),
      "border-style": "dotted"
    });
  },

  events: {
    "fileLinkAdded": "qx.event.type.Data"
  },

  members: {}
});
