/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * @asset(osparc/mock_clusters.json")
 */

qx.Class.define("osparc.store.Clusters", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    clusters: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeClusters"
    }
  },

  members: {
    fetchClusters: function() {
      return osparc.utils.Utils.fetchJSON("/resource/osparc/mock_clusters.json")
        .then(clustersData => {
          if ("clusters" in clustersData) {
            clustersData["clusters"].forEach(clusterData => {
              this.addCluster(clusterData);
            });
          }
          return this.getClusters();
        })
        .catch(err => console.error(err));
    },

    addCluster: function(clusterData) {
      const clusters = this.getClusters();
      const index = clusters.findIndex(t => t.getClusterId() === clusterData["cluster_id"]);
      if (index === -1) {
        const cluster = new osparc.data.Cluster(clusterData);
        clusters.push(cluster);
        this.fireDataEvent("changeClusters");
        return cluster;
      }
      return null;
    },

    removeClusters: function() {
      const clusters = this.getClusters();
      clusters.forEach(cluster => cluster.dispose());
      this.fireDataEvent("changeClusters");
    },
  }
});
