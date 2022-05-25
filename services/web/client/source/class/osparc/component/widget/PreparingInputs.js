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

    const list = this.__monitoredNodesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    this._add(list);
    this.setPreparingNodes(preparingNodes);

    const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
    loggerView.getChildControl("pin-node").exclude();
    this._add(loggerView, {
      flex: 1
    });
  },

  properties: {
    preparingNodes: {
      check: "Array",
      init: null,
      apply: "__applyPreparingNodes"
    }
  },

  members: {
    __preparingNodes: null,
    __monitoredNodesList: null,

    __applyPreparingNodes: function(preparingNodes) {
      preparingNodes.forEach(preparingNode => {
        [
          "changeRunning",
          "changeOutput"
        ].forEach(changeEvent => preparingNode.getStatus().addListener(changeEvent, () => this.__updateMonitoredNodesList()));
      });
      this.__updateMonitoredNodesList();
    },

    __updateMonitoredNodesList: function() {
      this.__monitoredNodesList.removeAll();
      const preparingNodes = this.getPreparingNodes();
      this.__monitoredNodesList.add(new qx.ui.basic.Label(this.tr("Preparing:")));
      if (preparingNodes && preparingNodes.length) {
        preparingNodes.forEach(node => {
          if (osparc.data.model.NodeStatus.isCompNodeReady(node)) {
            this.__monitoredNodesList.add(new qx.ui.basic.Label("+ " + node.getLabel()));
          } else {
            this.__monitoredNodesList.add(new qx.ui.basic.Label("- " + node.getLabel()));
          }
        });
      }
    }
  }
});
