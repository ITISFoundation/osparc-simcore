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

qx.Class.define("osparc.study.FunctionPreview", {
  extend: qx.ui.core.Widget,

  /**
   * @param func {osparc.data.model.Function} Function model
   */
  construct: function(func) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__buildPreview(func);
  },

  members: {
    __buildPreview: function(func) {
      const wbData = func.getWorkbenchData();
      const functionUiData = func.getFunctionUIData();
      const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview2(wbData, functionUiData["workbench"] || {});
      workbenchUIPreview.setMaxHeight(550);
      this._add(workbenchUIPreview);
    }
  }
});
