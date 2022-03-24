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

qx.Class.define("osparc.component.cluster.ClusterMiniView", {
  extend: qx.ui.core.Widget,

  construct: function(clusterId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox().set({
      alignY: "middle"
    }));

    this.__clusterId = clusterId;

    const grid = new qx.ui.layout.Grid(2, 2);
    const miniGrid = this.__miniGrid = new qx.ui.container.Composite(grid);
    this._add(miniGrid);

    this.__fetchDetails();
    // Poll every 5 seconds
    const interval = 5000;
    const timer = this.__timer = new qx.event.Timer(interval);
    timer.addListener("interval", () => this.__fetchDetails(), this);
    timer.start();

    this.set({
      cursor: "pointer"
    });
    this.addListener("tap", () => osparc.utils.Clusters.popUpClustersDetails(this.__clusterId), this);

    const description = "CPU: 4/6<br>CPU: 4/6<br>CPU: 4/6<br>";
    const hint = new osparc.ui.hint.Hint(this, description).set({
      active: false
    });
    const showHint = () => hint.show();
    const hideHint = () => hint.exclude();
    this.addListener("mouseover", showHint);
    [
      "mouseout",
      "tap"
    ].forEach(e => this.addListener(e, hideHint));
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
    __timer: null,
    __clusterDetailsLayout: null,
    __miniGrid: null,

    __fetchDetails: function() {
      const params = {
        url: {
          "cid": this.__clusterId
        }
      };
      osparc.data.Resources.fetch("clusters", "details", params)
        .then(clusterDetails => this.__updateWorkersDetails(clusterDetails));
    },

    __updateWorkersDetails: function(clusterDetails) {
      this.__updateMiniView(clusterDetails);
    },

    __updateMiniView: function(clusterDetails) {
      const miniGrid = this.__miniGrid;
      miniGrid.removeAll();
      const resources = {
        cpu: {
          metric: "cpu",
          resource: "CPU",
          available: 0,
          used: 0
        },
        ram: {
          metric: "memory",
          resource: "RAM",
          available: 0,
          used: 0
        },
        gpu: {
          metric: "gpu",
          resource: "GPU",
          available: 0,
          used: 0
        }
      };
      Object.keys(resources).forEach(resourceKey => {
        const resource = resources[resourceKey];
        osparc.utils.Clusters.accumulateWorkersResources(clusterDetails.scheduler.workers, resource);
      });

      Object.keys(resources).forEach((resourceKey, idx) => {
        const resourceInfo = resources[resourceKey];
        const label = new qx.ui.basic.Label(resourceInfo.resource).set({
          font: "text-9"
        });
        miniGrid.add(label, {
          row: idx,
          column: 0
        });
        const progressBar = new qx.ui.indicator.ProgressBar(resourceInfo.used, resourceInfo.available).set({
          height: 9,
          width: 60
        });
        progressBar.getChildControl("progress").set({
          backgroundColor: "visual-blue"
        });
        miniGrid.add(progressBar, {
          row: idx,
          column: 1
        });
      });
    }
  },

  destruct: function() {
    this.__timer.stop();
  }
});
