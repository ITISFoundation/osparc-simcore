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
  type: "static",

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
          resource.used += used/available;
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
    }
  }
});
