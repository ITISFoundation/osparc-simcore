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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox().set({
      alignY: "middle"
    }));

    const grid = new qx.ui.layout.Grid(2, 2);
    const miniGrid = this.__miniGrid = new qx.ui.container.Composite(grid).set({
      minWidth: 1
    });
    this._add(miniGrid);

    this.__listenToClusterDetails();

    this.set({
      cursor: "pointer"
    });
    this.addListener("tap", () => osparc.utils.Clusters.popUpClustersDetails(this.__clusterId), this);

    const hint = this.__hint = new osparc.ui.hint.Hint(this).set({
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
    __clusterDetailsLayout: null,
    __miniGrid: null,
    __hint: null,

    setClusterId: function(clusterId) {
      const clusters = osparc.utils.Clusters.getInstance();
      if (this.__clusterId !== null) {
        clusters.stopFetchingDetails(this.__clusterId);
      }
      this.__clusterId = clusterId;
      clusters.startFetchingDetails(clusterId);
    },

    __listenToClusterDetails: function() {
      const clusters = osparc.utils.Clusters.getInstance();
      clusters.addListener("clusterDetailsReceived", e => {
        const data = e.getData();
        if (this.__clusterId === data.clusterId) {
          if ("error" in data) {
            this.__detailsCallFailed();
          } else {
            const clusterDetails = data.clusterDetails;
            this.__updateWorkersDetails(clusterDetails);
          }
        }
      });
    },

    __showFailedBulb: function() {
      const miniGrid = this.__miniGrid;
      miniGrid.removeAll();

      const clusterStatusImage = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/lightbulb/16",
        alignY: "middle",
        alignX: "center",
        paddingLeft: 3,
        textColor: "failed-red"
      });
      miniGrid.add(clusterStatusImage, {
        row: 0,
        column: 0
      });
    },

    __detailsCallFailed: function() {
      this.__showFailedBulb();
      this.__hint.setText(this.tr("Connection failed"));
    },

    __updateWorkersDetails: function(clusterDetails) {
      const miniGrid = this.__miniGrid;
      miniGrid.removeAll();

      const workers = clusterDetails.scheduler.workers;
      if (Object.keys(workers).length === 0) {
        this.__showFailedBulb();
        this.__hint.setText(this.tr("No workers found in this cluster"));
        return;
      }

      const resources = {
        cpu: {
          metric: "cpu",
          resource: "CPU",
          icon: "@FontAwesome5Solid/microchip/10",
          available: 0,
          used: 0
        },
        ram: {
          metric: "memory",
          resource: "RAM",
          icon: "@MaterialIcons/memory/10",
          available: 0,
          used: 0
        },
        gpu: {
          metric: "gpu",
          resource: "GPU",
          icon: "@FontAwesome5Solid/server/10",
          available: 0,
          used: 0
        }
      };
      Object.keys(resources).forEach(resourceKey => {
        const resource = resources[resourceKey];
        osparc.utils.Clusters.accumulateWorkersResources(workers, resource);
      });
      this.__updateMiniView(resources);
      this.__updateHint(resources);
    },

    __updateMiniView: function(resources) {
      const miniGrid = this.__miniGrid;
      Object.keys(resources).forEach((resourceKey, idx) => {
        const resourceInfo = resources[resourceKey];
        if (resourceInfo.available === 0) {
          return;
        }
        const icon = new qx.ui.basic.Image(resourceInfo.icon);
        miniGrid.add(icon, {
          row: idx,
          column: 0
        });
        const progressBar = new qx.ui.indicator.ProgressBar(resourceInfo.used, resourceInfo.available).set({
          height: 10,
          width: 60
        });
        osparc.utils.Utils.hideBorder(progressBar);
        progressBar.getChildControl("progress").set({
          backgroundColor: "visual-blue"
        });
        miniGrid.add(progressBar, {
          row: idx,
          column: 1
        });
      });
    },

    __updateHint: function(resources) {
      let text = "";
      Object.keys(resources).forEach(resourceKey => {
        const resourceInfo = resources[resourceKey];
        if (resourceInfo.available === 0) {
          return;
        }
        text += resourceInfo.resource + ": ";
        if (resourceKey === "cpu") {
          text += osparc.utils.Utils.toTwoDecimals(resourceInfo.used*resourceInfo.available/100) + " / " + resourceInfo.available;
        } else if (resourceKey === "ram") {
          text += osparc.utils.Utils.bytesToGB(resourceInfo.used) + "GB / " + osparc.utils.Utils.bytesToGB(resourceInfo.available) + "GB";
        } else {
          text += resourceInfo.used + " / " + resourceInfo.available;
        }
        text += "<br>";
      });
      this.__hint.setText(text);
    }
  },

  destruct: function() {
    osparc.utils.Clusters.getInstance().stopFetchingDetails(this.__clusterId);
  }
});
