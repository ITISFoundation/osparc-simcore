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
    const list = this.__monitoredNodesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    this._add(list);
    this.__updateMonitoredNodesList();
    preparingNodes.forEach(preparingNode => {
      [
        "changeRunning",
        "changeOutput"
      ].forEach(changeEvent => preparingNode.getStatus().addListener(changeEvent, () => this.__updateMonitoredNodesList()));
    });

    const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
    loggerView.getChildControl("pin-node").exclude();
    this._add(loggerView, {
      flex: 1
    });
  },

  members: {
    __preparingNodes: null,
    __monitoredNodesList: null,

    __updateMonitoredNodesList: function() {
      this.__monitoredNodesList.removeAll();
      this.__preparingNodes.forEach(node => {
        if (!osparc.data.model.NodeStatus.isCompNodeReady(node)) {
          this.__monitoredNodesList.add(new qx.ui.basic.Label("- " + node.getLabel()));
        }
      });
    }
  }
});
