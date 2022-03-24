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

/**
 *   Collection of methods for dealing with clusters.
 *
 * *Example*
 */

qx.Class.define("osparc.utils.Clusters", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);
    this.__fetchDetailsTimers = [];
  },

  statics: {
    popUpClustersDetails: function(clusterId) {
      const clusters = new osparc.component.cluster.ClustersDetails(clusterId);
      osparc.ui.window.Window.popUpInWindow(clusters, qx.locale.Manager.tr("Clusters & Workers"), 650, 600);
    },

    getResourcesAttribute: function(worker, attributeKey) {
      if (attributeKey in worker.resources) {
        return worker.resources[attributeKey];
      }
      return "-";
    },

    getMetricsAttribute: function(worker, attributeKey) {
      if (attributeKey in worker.metrics) {
        return worker.metrics[attributeKey];
      }
      return "-";
    },

    accumulateWorkersResources: function(workers, resource) {
      Object.keys(workers).forEach(workerUrl => {
        const worker = workers[workerUrl];
        const available = this.getResourcesAttribute(worker, resource.resource);
        if (available === "-") {
          return;
        }
        resource.available += available;
        const used = this.getMetricsAttribute(worker, resource.metric);
        if (resource.metric === "cpu") {
          resource.used += osparc.utils.Utils.toTwoDecimals(used*available/100);
        } else {
          resource.used += used;
        }
      });
    },

    populateClustersSelectBox: function(clustersSelectBox) {
      clustersSelectBox.removeAll();

      const store = osparc.store.Store.getInstance();
      const clusters = store.getClusters();
      if (clusters) {
        const itemDefault = new qx.ui.form.ListItem().set({
          label: "default",
          toolTipText: "default cluster"
        });
        itemDefault.id = 0;
        clustersSelectBox.add(itemDefault);
        clusters.forEach(cluster => {
          if (!("name" in cluster)) {
            return;
          }
          const item = new qx.ui.form.ListItem().set({
            label: cluster["name"],
            toolTipText: cluster["type"] + "\n" + cluster["description"],
            allowGrowY: false
          });
          item.id = cluster["id"];
          clustersSelectBox.add(item);
        });
      }
      return clusters;
    },

    fetchDetails: function(cid) {
      const params = {
        url: {
          cid
        }
      };
      osparc.data.Resources.fetch("clusterDetails", params);
    }
  },

  members: {
    __fetchDetailsTimers: null,

    startFetchDetailsTimer: function(clusterId, interval = 3000) {
      const fetchDetailsTimer = this.__fetchDetailsTimers.find(timer => timer.clusterId === clusterId);
      if (fetchDetailsTimer) {
        fetchDetailsTimer.counter++;
        return;
      }
      this.self().fetchDetails(clusterId);
      const timer = new qx.event.Timer(interval);
      timer.clusterId = clusterId;
      timer.counter = 1;
      timer.addListener("interval", () => this.self().fetchDetails(clusterId), this);
      timer.start();
      this.__fetchDetailsTimers.push(timer);
    },

    stopFetchDetailsTimer: function(clusterId) {
      const idx = this.__fetchDetailsTimers.findIndex(timer => timer.clusterId === clusterId);
      if (idx > 1) {
        const fetchDetailsTimer = this.__fetchDetailsTimers[idx];
        fetchDetailsTimer.counter--;
        if (fetchDetailsTimer.counter === 0) {
          fetchDetailsTimer.stop();
          this.__fetchDetailsTimers.splice(idx, 1);
        }
      }
    }
  }
});
