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

    const clusterDetailsLayout = this.__clusterDetailsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
    this._add(clusterDetailsLayout);

    const grid = new qx.ui.layout.Grid(5, 5);
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

      const clusterIdLabel = new qx.ui.basic.Label("C-" + this.__clusterId);
      clusterDetailsLayout.add(clusterIdLabel);

      const clusterStatusLabel = new qx.ui.basic.Label(this.tr("Status: ") + clusterDetails.scheduler.status);
      clusterDetailsLayout.add(clusterStatusLabel);

      const clusterLinkLabel = new qx.ui.basic.Label(this.tr("Link: ") + clusterDetails["dashboard_link"]);
      clusterDetailsLayout.add(clusterLinkLabel);
    },

    __populateWorkers: function(clusterDetails) {
      this.__workersGrid.removeAll();
      this.__populateWorkersHeader();
      this.__populateWorkersDetails(clusterDetails);
    },

    __populateWorkersHeader: function() {
      const workersGrid = this.__workersGrid;

      const row = 0;
      const workerIdLabel = new qx.ui.basic.Label("Cluster ID");
      workersGrid.add(workerIdLabel, {
        row,
        column: this.self().GRID_POS.ID
      });

      const workerNameLabel = new qx.ui.basic.Label("Name");
      workersGrid.add(workerNameLabel, {
        row,
        column: this.self().GRID_POS.LABEL
      });

      const workerCPULabel = new qx.ui.basic.Label("CPU");
      workersGrid.add(workerCPULabel, {
        row,
        column: this.self().GRID_POS.CPU
      });

      const workerRAMLabel = new qx.ui.basic.Label("RAM");
      workersGrid.add(workerRAMLabel, {
        row,
        column: this.self().GRID_POS.RAM
      });

      const workerGPULabel = new qx.ui.basic.Label("GPU");
      workersGrid.add(workerGPULabel, {
        row,
        column: this.self().GRID_POS.GPU
      });

      const workerMPILabel = new qx.ui.basic.Label("MPI");
      workersGrid.add(workerMPILabel, {
        row,
        column: this.self().GRID_POS.MPI
      });
    },

    __populateWorkersDetails: function(clusterDetails) {
      const workersGrid = this.__workersGrid;

      let row = 1;
      Object.keys(clusterDetails.scheduler.workers).forEach((workerUrl, idx) => {
        const worker = clusterDetails.scheduler.workers[workerUrl];
        row++;

        const workerIdLabel = new qx.ui.basic.Label("W-" + idx);
        workersGrid.add(workerIdLabel, {
          row,
          column: this.self().GRID_POS.ID
        });

        const workerNameLabel = new qx.ui.basic.Label(worker.name);
        workersGrid.add(workerNameLabel, {
          row,
          column: this.self().GRID_POS.LABEL
        });

        const workerCPULabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "cpu") + "/" + this.self().getResourcesAttribute(worker, "CPU")
        });
        workersGrid.add(workerCPULabel, {
          row,
          column: this.self().GRID_POS.CPU
        });

        const workerRAMLabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "memory") + "/" + this.self().getResourcesAttribute(worker, "RAM")
        });
        workersGrid.add(workerRAMLabel, {
          row,
          column: this.self().GRID_POS.RAM
        });

        const workerGPULabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "gpu") + "/" + this.self().getResourcesAttribute(worker, "GPU")
        });
        workersGrid.add(workerGPULabel, {
          row,
          column: this.self().GRID_POS.GPU
        });

        const workerMPILabel = new qx.ui.basic.Label().set({
          value: this.self().getMetricsAttribute(worker, "mpi") + "/" + this.self().getResourcesAttribute(worker, "MPI")
        });
        workersGrid.add(workerMPILabel, {
          row,
          column: this.self().GRID_POS.MPI
        });
      });
    }
  },

  destruct: function() {
    this.__timer.stop();
  }
});
