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

  construct: function(monitoredNodes = []) {
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
    this.setMonitoredNodes(monitoredNodes);

    const loggerView = this.__loggerView = new osparc.component.widget.logger.LoggerView();
    loggerView.getChildControl("pin-node").exclude();
    this._add(loggerView, {
      flex: 1
    });
  },

  properties: {
    monitoredNodes: {
      check: "Array",
      init: null,
      apply: "__applyMonitoredNodes",
      event: "changeMonitoredNodes"
    },

    preparingNodes: {
      check: "Array",
      init: null
    }
  },

  events: {
    "changePreparingNodes": "qx.event.type.Event"
  },

  members: {
    __preparingNodes: null,
    __monitoredNodesList: null,

    __applyMonitoredNodes: function(monitoredNodes) {
      monitoredNodes.forEach(monitoredNode => {
        [
          "changeRunning",
          "changeOutput"
        ].forEach(changeEvent => monitoredNode.getStatus().addListener(changeEvent, () => {
          this.__updateMonitoredNodesList();
          this.__updatePreparingNodes();
        }));
      });
      this.__updateMonitoredNodesList();
      this.setPreparingNodes(monitoredNodes);
    },

    __updateMonitoredNodesList: function() {
      this.__monitoredNodesList.removeAll();
      const monitoredNodes = this.getMonitoredNodes();
      this.__monitoredNodesList.add(new qx.ui.basic.Label(this.tr("Monitoring:")));
      if (monitoredNodes && monitoredNodes.length) {
        monitoredNodes.forEach(node => {
          if (osparc.data.model.NodeStatus.isCompNodeReady(node)) {
            this.__monitoredNodesList.add(new qx.ui.basic.Label("+ " + node.getLabel()));
          } else {
            this.__monitoredNodesList.add(new qx.ui.basic.Label("- " + node.getLabel()));
          }
        });
      }
    },

    __updatePreparingNodes: function() {
      const preparingNodes = this.getPreparingNodes();
      for (let i = preparingNodes.length - 1; i >= 0; i--) {
        if (osparc.data.model.NodeStatus.isCompNodeReady(preparingNodes[i])) {
          preparingNodes.splice(i, 1);
        }
      }
      this.setPreparingNodes(preparingNodes);
      this.fireEvent("changePreparingNodes");
    }
  }
});
