/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.BaseView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this._buildLayout();
  },

  statics: {
    createGroupBox: function(title) {
      const box = new qx.ui.groupbox.GroupBox(title).set({
        layout: new qx.ui.layout.VBox(5)
      });
      box.getChildControl("legend").set({
        font: "text-14"
      });
      box.getChildControl("frame").set({
        backgroundColor: "transparent",
        marginTop: 10,
        padding: 2
      });
      return box;
    }
  }
});
