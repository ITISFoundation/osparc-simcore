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

qx.Class.define("osparc.store.Jobs", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    jobs: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeJobs"
    }
  },

  members: {
    fetchJobs: function() {
      return osparc.data.Resources.get("jobs")
        .then(jobsData => {
          jobsData.forEach(jobData => {
            const interval = 1000;
            this.addJob(jobData, interval);
          });
        })
        .catch(err => console.error(err));
    },

    addJob: function(jobData, interval = 1000) {
      const jobs = this.getJobs();
      const index = jobs.findIndex(t => t.getJobId() === jobData["job_id"]);
      if (index === -1) {
        const job = new osparc.data.Job(jobData, interval);
        jobs.push(job);
        return job;
      }
      return null;
    },

    createJob: function(fetchPromise, interval) {
      return new Promise((resolve, reject) => {
        fetchPromise
          .then(jobData => {
            if ("status_href" in jobData) {
              const job = this.addJob(jobData, interval);
              resolve(job);
            } else {
              throw Error("Status missing");
            }
          })
          .catch(err => reject(err));
      });
    },

    removeJobs: function() {
      const jobs = this.getJobs();
      jobs.forEach(job => job.dispose());
    },
  }
});
