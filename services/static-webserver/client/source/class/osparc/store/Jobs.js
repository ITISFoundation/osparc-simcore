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
 * @asset(osparc/mock_jobs.json")
 */

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
      return osparc.utils.Utils.fetchJSON("/resource/osparc/mock_jobs.json")
        .then(jobsData => {
          if ("jobs" in jobsData) {
            jobsData["jobs"].forEach(jobData => {
              this.addJob(jobData);
            });
          }
          return this.getJobs();
        })
        .catch(err => console.error(err));
    },

    fetchJobInfo: function(jobId) {
      return osparc.utils.Utils.fetchJSON("/resource/osparc/mock_jobs.json")
        .then(jobsData => {
          if ("jobs_info" in jobsData && jobId in jobsData["jobs_info"]) {
            return jobsData["jobs_info"][jobId];
          }
          return null;
        })
        .catch(err => console.error(err));
    },

    addJob: function(jobData) {
      const jobs = this.getJobs();
      const index = jobs.findIndex(t => t.getJobId() === jobData["job_id"]);
      if (index === -1) {
        const job = new osparc.data.Job(jobData);
        jobs.push(job);
        this.fireEvent("changeJobs");
        return job;
      }
      return null;
    },

    removeJobs: function() {
      const jobs = this.getJobs();
      jobs.forEach(job => job.dispose());
      this.fireEvent("changeJobs");
    },
  }
});
