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

  construct: function(study) {
    this.base(arguments);

    osparc.utils.Utils.setIdToWidget(this, "preparingInputsView");

    this._setLayout(new qx.ui.layout.VBox(10));

    const text = this.tr("In order to move to this step, we need to prepare some inputs for you.<br>Here you can check the logs of the progress:");
    const title = new qx.ui.basic.Label(text).set({
      font: "text-14",
      rich: true
    });
    this._add(title);

    const startStopButtons = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
      marginLeft: 50
    });
    const runAllButton = this.__getRunAllButton();
    startStopButtons.add(runAllButton);
    const stopButton = this.__getStopButton();
    startStopButtons.add(stopButton);
    this._add(startStopButtons);

    const list = this.__monitoredNodesList = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
    this._add(list);
    this.setMonitoredNodes([]);

    const loggerLayout = this.__loggerLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    this._add(loggerLayout, {
      flex: 1
    });

    study.addListener("changePipelineRunning", () => this.__updateRunButtonsStatus(study));
    this.__updateRunButtonsStatus(study);
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
    "changePreparingNodes": "qx.event.type.Data",
    "startPartialPipeline": "qx.event.type.Data",
    "stopPipeline": "qx.event.type.Event"
  },

  members: {
    __monitoredNodesList: null,
    __runAllButton: null,
    __stopButton: null,

    __getRunAllButton: function() {
      const runAllButton = this.__runAllButton = new osparc.ui.form.FetchButton(this.tr("Run all")).set({
        minWidth: 80,
        maxWidth: 80,
        alignX: "center"
      });
      runAllButton.addListener("execute", () => {
        const monitoredNodes = this.getMonitoredNodes();
        if (monitoredNodes && monitoredNodes.length) {
          const moniteoredNodesIds = monitoredNodes.map(monitoredNode => monitoredNode.getNodeId());
          this.fireDataEvent("startPartialPipeline", moniteoredNodesIds);
        }
      });
      return runAllButton;
    },

    __getStopButton: function() {
      const stopButton = this.__stopButton = new osparc.ui.form.FetchButton(this.tr("Stop")).set({
        minWidth: 80,
        maxWidth: 80,
        alignX: "center"
      });
      stopButton.addListener("execute", () => this.fireEvent("stopPipeline"), this);
      return stopButton;
    },

    __updateRunButtonsStatus: function(study) {
      const isPipelineRunning = study.isPipelineRunning();
      this.__runAllButton.setFetching(isPipelineRunning);
      this.__stopButton.setEnabled(isPipelineRunning);
    },

    __applyMonitoredNodes: function(monitoredNodes) {
      monitoredNodes.forEach(monitoredNode => {
        [
          "changeRunning",
          "changeOutput"
        ].forEach(changeEvent => {
          monitoredNode.getStatus().addListener(changeEvent, () => this.__updatePreparingNodes());
        });
      });
      this.__updateMonitoredNodesList();
      this.__updatePreparingNodes();
    },

    __updateMonitoredNodesList: function() {
      this.__monitoredNodesList.removeAll();
      const monitoredNodes = this.getMonitoredNodes();
      if (monitoredNodes && monitoredNodes.length) {
        const group = new qx.ui.form.RadioGroup();
        group.addListener("changeSelection", e => {
          const selectedButton = e.getData()[0];
          this.__loggerLayout.removeAll();
          const nodeLogger = selectedButton.node.getLogger();
          nodeLogger.getChildControl("pin-node").exclude();
          this.__loggerLayout.add(nodeLogger);
        }, this);
        monitoredNodes.forEach(node => {
          const nodeLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));

          const showLoggerBtn = new qx.ui.form.ToggleButton(this.tr("Logs"));
          showLoggerBtn.node = node;
          nodeLayout.add(showLoggerBtn);
          group.add(showLoggerBtn);
          if (group.getSelection().length === 0) {
            group.setSelection([showLoggerBtn]);
          }

          const rerunBtn = new osparc.ui.form.FetchButton(this.tr("Re-run")).set({
            minWidth: 80,
            maxWidth: 80,
            alignX: "center"
          });
          rerunBtn.addListener("execute", () => this.fireDataEvent("startPartialPipeline", [node.getNodeId()]), this);
          nodeLayout.add(rerunBtn);

          const checkRerunStatus = () => {
            const nodeRunningStatus = node.getStatus().getRunning();
            const fetching = [
              "PUBLISHED",
              "PENDING",
              "STARTED",
              "WAITING_FOR_RESOURCES"
            ].includes(nodeRunningStatus);
            rerunBtn.setFetching(fetching);
            const rerunnable = [
              "FAILED",
              "ABORTED",
              "SUCCESS"
            ].includes(nodeRunningStatus);
            const isPipelineRunning = node.getStudy().isPipelineRunning();
            rerunBtn.setEnabled(rerunnable && !(isPipelineRunning === true));
          };
          node.getStatus().addListener("changeRunning", () => checkRerunStatus());
          node.getStudy().addListener("changePipelineRunning", () => checkRerunStatus());
          checkRerunStatus();

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
