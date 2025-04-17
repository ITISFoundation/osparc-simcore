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
    fetchJobs: function(orderBy = {
      field: "submitted_at",
      direction: "desc"
    }) {
      const params = {
        url: {
          orderBy: JSON.stringify(orderBy),
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("jobs", params)
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

    fetchSubJobs: function(studyId, orderBy = {
      field: "submitted_at",
      direction: "desc"
    }) {
      const params = {
        url: {
          studyId,
          orderBy: JSON.stringify(orderBy),
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("subJobs", params)
        .then(jobsData => {
          if ("jobs_info" in jobsData && studyId in jobsData["jobs_info"]) {
            return jobsData["jobs_info"][studyId];
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
        this.fireDataEvent("changeJobs");
        return job;
      }
      return null;
    },

    removeJobs: function() {
      const jobs = this.getJobs();
      jobs.forEach(job => job.dispose());
      this.fireDataEvent("changeJobs");
    },
  }
});
