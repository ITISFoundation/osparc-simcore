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

qx.Class.define("osparc.component.cluster.ClusterWorkers", {
  extend: qx.ui.core.Widget,

  construct: function(clusterId) {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(5, 8);
    for (let i=0; i<Object.keys(this.self().GRID_POS).length; i++) {
      grid.setColumnFlex(i, 1);
    }
    this._setLayout(grid);

    this.__clusterId = clusterId;
    this.__startFetchingDetails();
  },

  statics: {
    GRID_POS: {
      ICON: 0,
      CPU: 1,
      RAM: 2,
      GPU: 3
    }
  },

  properties: {
    clusterStatus: {
      check: ["unknown", "connected", "failed"],
      init: "unknown",
      event: "changeClusterStatus"
    }
  },

  members: {
    __clusterId: null,

    __startFetchingDetails: function() {
      const clusters = osparc.utils.Clusters.getInstance();
      clusters.addListener("clusterDetailsReceived", e => {
        const data = e.getData();
        if (this.__clusterId === data.clusterId) {
          if ("error" in data) {
            this.setClusterStatus("failed");
          } else {
            this.setClusterStatus("connected");
            this.populateWorkersDetails(data.clusterDetails);
          }
        }
      });
      clusters.startFetchingDetails(this.__clusterId);
    },

    populateWorkersDetails: function(clusterDetails) {
      this._removeAll();

      if (Object.keys(clusterDetails.scheduler.workers).length === 0) {
        const workerNameLabel = new qx.ui.basic.Label(this.tr("No workers found in this cluster"));
        this._add(workerNameLabel, {
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
          label: this.tr("Memory (GB)"),
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
      const gridW = this.__computedLayout ? this.__computedLayout.width - 15 : 600;
      Object.keys(clusterDetails.scheduler.workers).forEach(workerUrl => {
        const worker = clusterDetails.scheduler.workers[workerUrl];

        const img = new qx.ui.basic.Image().set({
          source: "@FontAwesome5Solid/server/24",
          toolTipText: worker.name,
          textColor: "ready-green",
          paddingTop: 50
        });
        this._add(img, {
          row,
          column: this.self().GRID_POS.ICON
        });

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
          } else if (plotKey === "ram") {
            gaugeData.value = osparc.utils.Utils.bytesToGB(used);
            gaugeData.gauge.axis.range[1] = osparc.utils.Utils.bytesToGB(available);
          } else {
            gaugeData.value = used;
            gaugeData.gauge.axis.range[1] = available;
          }
          const layout = osparc.wrapper.Plotly.getDefaultLayout();
          const plotId = "ClusterDetails_" + plotKey + "-" + row;
          const w = parseInt(gridW/Object.keys(plots).length);
          const h = parseInt(w*0.75);
          console.log(gridW, w, h);
          const plot = new osparc.component.widget.PlotlyWidget(plotId, gaugeDatas, layout).set({
            width: w,
            height: h
          });
          this._add(plot, {
            row,
            column: plotInfo.column
          });
        });
        row++;
      });
    }
  },

  destruct: function() {
    osparc.utils.Clusters.getInstance().stopFetchingDetails(this.__clusterId);
  }
});
