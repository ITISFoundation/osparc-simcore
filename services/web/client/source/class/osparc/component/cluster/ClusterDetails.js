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

qx.Class.define("osparc.component.cluster.ClusterDetails", {
  extend: qx.ui.core.Widget,

  construct: function(clusterId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    const clusterDetailsLayout = this.__clusterDetailsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
    this._add(clusterDetailsLayout);

    const grid = new qx.ui.layout.Grid(5, 8);
    grid.setColumnFlex(1, 1);
    const workersGrid = this.__workersGrid = new qx.ui.container.Composite(grid);
    this._add(workersGrid);

    this.__clusterId = clusterId;
    this.__startFetchingDetails();
  },

  statics: {
    GRID_POS: {
      CPU: 0,
      RAM: 1,
      GPU: 2
    }
  },

  members: {
    __clusterId: null,
    __clusterDetailsLayout: null,
    __workersGrid: null,

    __startFetchingDetails: function() {
      const clusters = osparc.utils.Clusters.getInstance();
      clusters.addListener("clusterDetailsReceived", e => {
        const data = e.getData();
        if (this.__clusterId === data.clusterId) {
          if ("error" in data) {
            this.__detailsCallFailed();
          } else {
            const clusterDetails = data.clusterDetails;
            this.__populateClusterDetails(clusterDetails);
            this.__populateWorkersDetails(clusterDetails);
          }
        }
      });
      clusters.startFetchingDetails(this.__clusterId);
    },

    __detailsCallFailed: function() {
      const clusterDetailsLayout = this.__clusterDetailsLayout;
      clusterDetailsLayout.removeAll();

      const clusterIdLabel = new qx.ui.basic.Label("C-" + this.__clusterId).set({
        marginRight: 35
      });
      clusterDetailsLayout.add(clusterIdLabel);

      const clusterStatusLabel = new qx.ui.basic.Label(this.tr("Status:"));
      clusterDetailsLayout.add(clusterStatusLabel);
      const clusterStatusImage = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/lightbulb/16",
        alignY: "middle",
        alignX: "center",
        paddingLeft: 3,
        textColor: "failed-red"
      });
      clusterDetailsLayout.add(clusterStatusImage);
    },

    __populateClusterDetails: function(clusterDetails) {
      const clusterDetailsLayout = this.__clusterDetailsLayout;
      clusterDetailsLayout.removeAll();

      const clusterIdLabel = new qx.ui.basic.Label("C-" + this.__clusterId).set({
        marginRight: 35
      });
      clusterDetailsLayout.add(clusterIdLabel);

      const clusterStatusLabel = new qx.ui.basic.Label(this.tr("Status:"));
      clusterDetailsLayout.add(clusterStatusLabel);
      const clusterStatus = clusterDetails.scheduler.status;
      const clusterStatusImage = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/lightbulb/16",
        alignY: "middle",
        alignX: "center",
        paddingLeft: 3,
        toolTipText: clusterStatus,
        textColor: clusterStatus === "running" ? "ready-green" : "failed-red"
      });
      clusterDetailsLayout.add(clusterStatusImage);

      if (this.__clusterId !== 0 && "dashboard_link" in clusterDetails) {
        const clusterLinkLabel = new qx.ui.basic.Label(this.tr("Link: ") + clusterDetails["dashboard_link"]);
        clusterDetailsLayout.add(clusterLinkLabel);
      }
    },

    __populateWorkersDetails: function(clusterDetails) {
      const workersGrid = this.__workersGrid;
      workersGrid.removeAll();

      if (Object.keys(clusterDetails.scheduler.workers).length === 0) {
        const workerNameLabel = new qx.ui.basic.Label(this.tr("No workers found in this cluster"));
        workersGrid.add(workerNameLabel, {
          row: 0,
          column: 0,
          colSpan: 4
        });
        return;
      }

      const plots = {
        cpu: {
          metric: "cpu",
          resource: "CPU",
          label: this.tr("CPU"),
          column: this.self().GRID_POS.CPU
        },
        ram: {
          metric: "memory",
          resource: "RAM",
          label: this.tr("Memory"),
          column: this.self().GRID_POS.RAM
        },
        gpu: {
          metric: "gpu",
          resource: "GPU",
          label: this.tr("GPU"),
          column: this.self().GRID_POS.GPU
        }
      };

      let row = 0;
      Object.keys(clusterDetails.scheduler.workers).forEach((workerUrl, idx) => {
        const worker = clusterDetails.scheduler.workers[workerUrl];
        row++;

        const workerNameLabel = new qx.ui.basic.Label("C-" + this.__clusterId + "_W-" + idx + ": " + worker.name);
        workersGrid.add(workerNameLabel, {
          row,
          column: 0,
          colSpan: 4
        });
        row++;
        Object.keys(plots).forEach(plotKey => {
          const plotInfo = plots[plotKey];
          const gaugeDatas = osparc.wrapper.Plotly.getDefaultGaugeData();
          const gaugeData = gaugeDatas[0];
          gaugeData.title.text = plotInfo.label.toLocaleString();
          const used = osparc.utils.Clusters.getMetricsAttribute(worker, plotInfo.metric);
          const available = osparc.utils.Clusters.getResourcesAttribute(worker, plotInfo.resource);
          if (available === "-") {
            gaugeData.value = "-";
          } else if (plotKey === "cpu") {
            gaugeData.value = osparc.utils.Utils.toTwoDecimals(used*available/100);
            gaugeData.gauge.axis.range[1] = available;
          } else {
            gaugeData.value = used;
            gaugeData.gauge.axis.range[1] = available;
          }
          const layout = osparc.wrapper.Plotly.getDefaultLayout();
          const plotId = "ClusterDetails_" + plotKey + "-" + row;
          const plot = new osparc.component.widget.PlotlyWidget(plotId, gaugeDatas, layout).set({
            width: 200,
            height: 160
          });
          workersGrid.add(plot, {
            row,
            column: plotInfo.column
          });
        });
      });
    }
  },

  destruct: function() {
    osparc.utils.Clusters.getInstance().stopFetchingDetails(this.__clusterId);
  }
});
