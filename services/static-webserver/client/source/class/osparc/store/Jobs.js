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
    jobsActive: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeJobsActive"
    }
  },

  statics: {
    SERVER_MAX_LIMIT: 49,
  },

  members: {
    fetchJobsActive: function(
      offset = 0,
      limit = this.self().SERVER_MAX_LIMIT,
      orderBy = {
        field: "submitted_at",
        direction: "desc"
      },
      resolveWResponse = false
    ) {
      const params = {
        url: {
          offset,
          limit,
          orderBy: JSON.stringify(orderBy),
        }
      };
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("jobsActive", "getPage", params, options)
        .then(jobsResp => {
          const jobsActive = [];
          if ("data" in jobsResp) {
            jobsResp["data"].forEach(jobActiveData => {
              jobsActive.push(this.__addJobActive(jobActiveData));
            });
          }
          if (resolveWResponse) {
            return jobsResp;
          }
          return jobsActive;
        })
        .catch(err => console.error(err));
    },

    fetchSubJobs: function(projectUuid) {
      const params = {
        url: {
          studyId: projectUuid,
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("subJobs", params)
        .then(subJobsData => {
          const subJobs = [];
          subJobsData.forEach(subJobData => {
            subJobs.push(this.addSubJob(subJobData));
          });
          return subJobs;
        })
        .catch(err => console.error(err));
    },

    __addJobActive: function(jobData) {
      const jobsActive = this.getJobsActive();
      const jobFound = jobsActive.find(job => job.getProjectUuid() === jobData["projectUuid"]);
      if (jobFound) {
        jobFound.updateJob(jobData);
        return jobFound;
      }
      const job = new osparc.data.Job(jobData);
      jobsActive.push(job);
      this.fireDataEvent("changeJobsActive");
      return job;
    },

    addSubJob: function(subJobData) {
      const jobs = this.getJobs();
      const jobFound = jobs.find(job => job.getProjectUuid() === subJobData["projectUuid"]);
      if (jobFound) {
        const subJob = jobFound.addSubJob(subJobData);
        return subJob;
      }
      return null;
    },

    getJob: function(projectUuid) {
      const jobs = this.getJobs();
      return jobs.find(job => job.getProjectUuid() === projectUuid);
    },
  }
});
