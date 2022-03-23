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
    this.__fetchDetails();
    // Poll every 5 seconds
    const interval = 5000;
    const timer = this.__timer = new qx.event.Timer(interval);
    timer.addListener("interval", () => this.__fetchDetails(), this);
    timer.start();
  },

  statics: {
    PLOT_WIDTH: 200,
    GRID_POS: {
      CPU: 0,
      RAM: 1,
      GPU: 2
    },

    getResourcesAttribute: function(worker, attribute) {
      if (attribute in worker.resources) {
        return worker.resources[attribute];
      }
      return "-";
    },

    getMetricsAttribute: function(worker, attribute) {
      if (attribute in worker.metrics) {
        return worker.metrics[attribute];
      }
      return "-";
    }
  },

  members: {
    __clusterId: null,
    __timer: null,
    __clusterDetailsLayout: null,
    __workersGrid: null,

    __fetchDetails: function() {
      const params = {
        url: {
          "cid": this.__clusterId
        }
      };
      osparc.data.Resources.fetch("clusters", "details", params)
        .then(clusterDetails => {
          this.__populateClusterDetails(clusterDetails);
          this.__populateWorkers(clusterDetails);
        });
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

      if (this.__clusterId !== 0) {
        const clusterLinkLabel = new qx.ui.basic.Label(this.tr("Link: ") + clusterDetails["dashboard_link"]);
        clusterDetailsLayout.add(clusterLinkLabel);
      }
    },

    __populateWorkers: function(clusterDetails) {
      this.__workersGrid.removeAll();
      this.__populateWorkersDetails(clusterDetails);
    },

    __populateWorkersDetails: function(clusterDetails) {
      const workersGrid = this.__workersGrid;

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

        const plots = {
          cpu: {
            label: this.tr("CPU"),
            metric: "cpu",
            resource: "CPU",
            column: this.self().GRID_POS.CPU
          },
          ram: {
            label: this.tr("Memory"),
            metric: "memory",
            resource: "RAM",
            column: this.self().GRID_POS.RAM
          },
          gpu: {
            label: this.tr("GPU"),
            metric: "gpu",
            resource: "GPU",
            column: this.self().GRID_POS.GPU
          }
        };
        Object.keys(plots).forEach(plotKey => {
          const plotInfo = plots[plotKey];
          const plotId = plotKey + "-" + row;
          const gaugeDatas = osparc.wrapper.Plotly.getDefaultGaugeData();
          const gaugeData = gaugeDatas[0];
          gaugeData.title.text = plotInfo.label.toLocaleString();
          let used = this.self().getMetricsAttribute(worker, plotInfo.metric);
          let available = this.self().getResourcesAttribute(worker, plotInfo.resource);
          if (available === "-") {
            gaugeData.value = "-";
          } else {
            gaugeData.value = used;
            gaugeData.gauge.axis.range[1] = available;
          }
          const layout = osparc.wrapper.Plotly.getDefaultLayout();
          const plot = new osparc.component.widget.PlotlyWidget(plotId, gaugeDatas, layout).set({
            width: parseInt(this.self().PLOT_WIDTH),
            height: parseInt(this.self().PLOT_WIDTH*0.8)
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
    this.__timer.stop();
  }
});
