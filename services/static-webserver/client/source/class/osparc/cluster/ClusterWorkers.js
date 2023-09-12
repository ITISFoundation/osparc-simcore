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

qx.Class.define("osparc.cluster.ClusterWorkers", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(5, 8);
    for (let i=0; i<Object.keys(this.self().GRID_POS).length; i++) {
      grid.setColumnFlex(i, 1);
    }
    this._setLayout(grid);
  },

  statics: {
    GRID_POS: {
      ICON: 0,
      CPU: 1,
      RAM: 2,
      GPU: 3
    }
  },

  members: {
    populateWorkersDetails: function(clusterDetails) {
      this._removeAll();

      if (clusterDetails === null) {
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
          usedResource: "CPU",
          resource: "CPU",
          label: this.tr("CPU"),
          column: this.self().GRID_POS.CPU
        },
        ram: {
          metric: "memory",
          usedResource: "RAM",
          resource: "RAM",
          label: this.tr("Memory (GB)"),
          column: this.self().GRID_POS.RAM
        },
        gpu: {
          metric: "gpu",
          usedResource: "GPU",
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
          source: "@FontAwesome5Solid/hdd/24",
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
          let used = osparc.utils.Clusters.getUsedResourcesAttribute(worker, plotInfo.usedResource);
          let available = osparc.utils.Clusters.getAvailableResourcesAttribute(worker, plotInfo.resource);
          if (plotKey === "ram") {
            used = osparc.utils.Utils.bytesToGB(used);
            available = osparc.utils.Utils.bytesToGB(available);
          }
          if (qx.lang.Type.isNumber(available)) {
            // orange > 80%
            gaugeData.gauge.steps = [{
              range: [0.8*available, available],
              color: qx.theme.manager.Color.getInstance().resolve("busy-orange"),
              thickness: 0.5
            }];
          }
          if (available === "-") {
            gaugeData.value = "-";
          } else {
            gaugeData.value = used;
            gaugeData.gauge.axis.range[1] = available;
          }
          const layout = osparc.wrapper.Plotly.getDefaultLayout();
          const plotId = "ClusterDetails_" + plotKey + "-" + row;
          const w = parseInt(gridW/Object.keys(plots).length);
          const h = parseInt(w*0.75);
          // hide plotly toolbar
          const config = {
            displayModeBar: false
          };
          const plot = new osparc.widget.PlotlyWidget(plotId, gaugeDatas, layout, config).set({
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
  }
});
