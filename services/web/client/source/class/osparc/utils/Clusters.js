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
        resource.used += used;
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
