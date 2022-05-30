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

    const loggerLayout = this.__loggerLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    this._add(loggerLayout, {
      flex: 1
    });
  },

  properties: {
    monitoredNodes: {
      check: "Array",
      init: null,
      apply: "__applyMonitoredNodes",
      event: "changeMonitoredNodes"
    }
  },

  events: {
    "changePreparingNodes": "qx.event.type.Data"
  },

  members: {
    __monitoredNodesList: null,

    popUpInWindow: function() {
      osparc.ui.window.Window.popUpInWindow(this, this.tr("Preparing Inputs"), 600, 500);
    },

    __applyMonitoredNodes: function(monitoredNodes) {
      monitoredNodes.forEach(monitoredNode => {
        [
          "changeRunning",
          "changeOutput"
        ].forEach(changeEvent => {
          monitoredNode.getStatus().addListener(changeEvent, () => {
            this.__updateMonitoredNodesList();
            this.__updatePreparingNodes();
          });
        });
      });
      this.__updateMonitoredNodesList();
    },

    __updateMonitoredNodesList: function() {
      this.__monitoredNodesList.removeAll();
      const monitoredNodes = this.getMonitoredNodes();
      this.__monitoredNodesList.add(new qx.ui.basic.Label(this.tr("Monitoring:")));
      const group = new qx.ui.form.RadioGroup();
      if (monitoredNodes && monitoredNodes.length) {
        monitoredNodes.forEach(node => {
          const nodeLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          const showLoggerBtn = new qx.ui.form.ToggleButton("Logger");
          showLoggerBtn.addListener("execute", e => {
            if (showLoggerBtn.getValue()) {
              this.__loggerLayout.removeAll();
              const nodeLogger = node.getLogger();
              this.__loggerLayout.add(nodeLogger);
            }
          });
          nodeLayout.add(showLoggerBtn);
          group.add(showLoggerBtn);
          if (group.getSelection().length === 0) {
            group.setSelection(showLoggerBtn);
          }
          const statusUI = new osparc.ui.basic.NodeStatusUI(node);
          nodeLayout.add(statusUI);
          nodeLayout.add(new qx.ui.basic.Label(node.getLabel()), {
            flex: 1
          });
          this.__monitoredNodesList.add(nodeLayout);
        });
      }
    },

    getPreparingNodes: function() {
      const preparingNodes = [];
      const monitoredNodes = this.getMonitoredNodes();
      monitoredNodes.forEach(monitoredNode => {
        if (!osparc.data.model.NodeStatus.isCompNodeReady(monitoredNode)) {
          preparingNodes.push(monitoredNode);
        }
      });
      return preparingNodes;
    },


    __updatePreparingNodes: function() {
      this.fireDataEvent("changePreparingNodes", this.getPreparingNodes().length);
    }
  }
});
