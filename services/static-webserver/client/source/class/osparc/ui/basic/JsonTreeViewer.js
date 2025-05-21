/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.ui.basic.JsonTreeViewer", {
  extend: qx.ui.core.Widget,

  /**
   * @param jsonObj {Object} Json object to be displayed by JsonTreeViewer
   */
  construct: function(jsonObj) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    if (jsonObj) {
      this.setJson(jsonObj);
    }
  },

  members: {
    setJson(jsonObj) {
      osparc.wrapper.JsonTreeViewer.getInstance().print(jsonObj, this.getContentElement());
    },
  }
});
