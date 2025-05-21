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
   * @param data {Object} Json object to be displayed by JsonTreeViewer
   */
  construct: function(data) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    if (data) {
      this.setJson(data);
    }
  },

  members: {
    setJson(data) {
      osparc.wrapper.JsonTreeViewer.getInstance().print(data, this.getContentElement());
    },
  }
});
