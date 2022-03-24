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
    const miniGrid = this.__miniGrid = new qx.ui.container.Composite(grid).set({
      minWidth: 1
    });
    this._add(miniGrid);

    this.__fetchDetails();
    // Fecth every 3 seconds
    const interval = 3000;
    const timer = this.__timer = new qx.event.Timer(interval);
    timer.addListener("interval", () => this.__fetchDetails(), this);
    timer.start();

    const store = osparc.store.Store.getInstance();
    store.addListener("changeClusters", e => {
      console.log("changeClusters", e.getData());
    }, this);

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
    __timer: null,
    __clusterDetailsLayout: null,
    __miniGrid: null,
    __hint: null,

    setClusterId: function(clusterId) {
      this.__clusterId = clusterId;
    },

    __fetchDetails: function() {
      if (osparc.utils.Utils.checkIsOnScreen(this)) {
        const params = {
          url: {
            "cid": this.__clusterId
          }
        };
        osparc.data.Resources.fetch("clusters", "details", params)
          .then(clusterDetails => this.__updateWorkersDetails(clusterDetails));
      }
    },

    __updateWorkersDetails: function(clusterDetails) {
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
        osparc.utils.Clusters.accumulateWorkersResources(clusterDetails.scheduler.workers, resource);
      });
      this.__updateMiniView(resources);
      this.__updateHint(resources);
    },

    __updateMiniView: function(resources) {
      const miniGrid = this.__miniGrid;
      miniGrid.removeAll();
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
          const b2gb = 1024*1024*1024;
          text += Math.round(100*resourceInfo.used/b2gb)/100 + "GB / " + Math.round(100*resourceInfo.available/b2gb)/100 + "GB";
        } else {
          text += resourceInfo.used + " / " + resourceInfo.available;
        }
        text += "<br>";
      });
      this.__hint.setText(text);
    }
  },

  destruct: function() {
    this.__timer.stop();
  }
});
