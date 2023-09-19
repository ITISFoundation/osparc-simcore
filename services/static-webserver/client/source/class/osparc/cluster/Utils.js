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

qx.Class.define("osparc.cluster.Utils", {
  extend: qx.core.Object,
  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.__clusterIds = [];
  },

  statics: {
    popUpClustersDetails: function(clusterId) {
      const clusters = new osparc.cluster.ClustersDetails(clusterId);
      osparc.ui.window.Window.popUpInWindow(clusters, qx.locale.Manager.tr("Clusters & Workers"), 650, 600);
    },

    getUsedResourcesAttribute: function(worker, attributeKey) {
      if (attributeKey in worker["used_resources"]) {
        return osparc.utils.Utils.toTwoDecimals(worker["used_resources"][attributeKey]);
      }
      return "-";
    },

    getAvailableResourcesAttribute: function(worker, attributeKey) {
      if (attributeKey in worker.resources) {
        return worker.resources[attributeKey];
      }
      return "-";
    },

    accumulateWorkersResources: function(workers, resource) {
      Object.keys(workers).forEach(workerUrl => {
        const worker = workers[workerUrl];
        const available = this.getAvailableResourcesAttribute(worker, resource.resource);
        if (available === "-") {
          return;
        }
        resource.available += available;
        const used = this.getUsedResourcesAttribute(worker, resource.usedResource);
        resource.used += used;
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
            const interval = 10000;
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
