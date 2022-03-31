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
    this.__clusterIds = [];
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
        clusters.forEach(cluster => {
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
    }
  },

  events: {
    "clusterDetailsReceived": "qx.event.type.Data"
  },

  members: {
    __clusterIds: null,
    __fetchDetailsTimers: null,

    __fetchDetails: function(cid) {
      const params = {
        url: {
          cid
        }
      };
      osparc.data.Resources.get("clusterDetails", params)
        .then(clusterDetails => {
          this.fireDataEvent("clusterDetailsReceived", {
            clusterId: cid,
            clusterDetails
          });
        })
        .catch(err => {
          console.error(err);
          this.fireDataEvent("clusterDetailsReceived", {
            clusterId: cid,
            error: err
          });
        })
        .finally(() => {
          if (this.__clusterIds.includes(cid)) {
            const interval = 3000;
            qx.event.Timer.once(() => this.__fetchDetails(cid), this, interval);
          }
        });
    },

    startFetchingDetails: function(clusterId) {
      const found = this.__clusterIds.includes(clusterId);
      this.__clusterIds.push(clusterId);
      if (!found) {
        this.__fetchDetails(clusterId);
      }
    },

    stopFetchingDetails: function(clusterId) {
      const idx = this.__clusterIds.indexOf(clusterId);
      if (idx > -1) {
        this.__clusterIds.splice(idx, 1);
      }
    }
  }
});
