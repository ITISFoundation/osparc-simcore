/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.widget.PreparingInputs", {
  extend: qx.ui.core.Widget,

  construct: function(preparingNodes = []) {
    this.base(arguments);

    // Layout
    this._setLayout(new qx.ui.layout.VBox(10));

    const text = this.tr("In order to move to this step, we need to prepare some inputs for you.<br>This might take a while, so enjoy checking the logs down here:");
    const title = new qx.ui.basic.Label(text).set({
      font: "text-14",
      rich: true
    });
    this._add(title);

    this.__preparingNodes = preparingNodes;
    this.__preparingNodes.forEach(node => this._add(new qx.ui.basic.Label("- " + node.getLabel())));

    const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
    loggerView.getChildControl("pin-node").exclude();
    this._add(loggerView);
  },

  members: {
    __preparingNodes: null
  }
});
