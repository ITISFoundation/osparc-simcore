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

  construct: function(clusterId, clusterDetails) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    const grid = new qx.ui.layout.Grid(10, 6);
    grid.setColumnFlex(1, 1);
    const clusterGrid = this.__clusterGrid = new qx.ui.container.Composite(grid);
    this._add(clusterGrid);

    console.log(clusterId, clusterDetails);
    this.__populateClusterDetails(clusterId, clusterDetails);
    this.__populateWorkersDetails(clusterId, clusterDetails);
  },

  statics: {
    GRID_POS: {
      ID: 0,
      LABEL: 1,
      CPU: 2,
      RAM: 3,
      GPU: 4,
      MPI: 5
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
    __clusterGrid: null,

    __populateClusterDetails: function(clusterId, clusterDetails) {
      const clusterDetailsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const clusterIdLabel = new qx.ui.basic.Label("C-" + clusterId);
      clusterDetailsLayout.add(clusterIdLabel);

      const clusterStatusLabel = new qx.ui.basic.Label(clusterDetails.scheduler.status);
      clusterDetailsLayout.add(clusterStatusLabel);

      const clusterLinkLabel = new qx.ui.basic.Label(clusterDetails["dashboard_link"]);
      clusterDetailsLayout.add(clusterLinkLabel);

      this._add(clusterDetailsLayout);
    },

    __populateWorkersDetails: function(clusterId, clusterDetails) {
      const clusterGrid = this.__clusterGrid;
      let row = 0;
      Object.keys(clusterDetails.scheduler.workers).forEach((workerUrl, idx) => {
        const worker = clusterDetails.scheduler.workers[workerUrl];
        row++;

        const workerIdLabel = new qx.ui.basic.Label("C-"+clusterId+"_W-" + idx);
        clusterGrid.add(workerIdLabel, {
          row,
          column: this.self().GRID_POS.ID
        });

        const workerNameLabel = new qx.ui.basic.Label(worker.name);
        clusterGrid.add(workerNameLabel, {
          row,
          column: this.self().GRID_POS.LABEL
        });

        const workerCPULabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "cpu") + "/" + this.self().getResourcesAttribute(worker, "CPU")
        });
        clusterGrid.add(workerCPULabel, {
          row,
          column: this.self().GRID_POS.CPU
        });

        const workerRAMLabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "memory") + "/" + this.self().getResourcesAttribute(worker, "RAM")
        });
        clusterGrid.add(workerRAMLabel, {
          row,
          column: this.self().GRID_POS.RAM
        });

        const workerGPULabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "gpu") + "/" + this.self().getResourcesAttribute(worker, "GPU")
        });
        clusterGrid.add(workerGPULabel, {
          row,
          column: this.self().GRID_POS.GPU
        });

        const workerMPILabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "mpi") + "/" + this.self().getResourcesAttribute(worker, "MPI")
        });
        clusterGrid.add(workerMPILabel, {
          row,
          column: this.self().GRID_POS.MPI
        });
      });
    }
  }
});
