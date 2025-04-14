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
            clustersData["clusters"].forEach(jobData => {
              this.addJob(jobData);
            });
          }
          return this.getClusters();
        })
        .catch(err => console.error(err));
    },

    addJob: function(jobData) {
      const clusters = this.getClusters();
      const index = clusters.findIndex(t => t.getJobId() === jobData["job_id"]);
      if (index === -1) {
        const job = new osparc.data.Job(jobData);
        clusters.push(job);
        this.fireDataEvent("changeClusters");
        return job;
      }
      return null;
    },

    removeClusters: function() {
      const clusters = this.getClusters();
      clusters.forEach(job => job.dispose());
      this.fireDataEvent("changeClusters");
    },
  }
});
