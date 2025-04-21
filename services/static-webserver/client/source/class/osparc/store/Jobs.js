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

  statics: {
    SERVER_MAX_LIMIT: 49,
  },

  members: {
    fetchJobs: function(
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
      return osparc.data.Resources.fetch("jobs", "getPage", params, options)
        .then(jobsResp => {
          const jobs = [];
          if ("data" in jobsResp) {
            jobsResp["data"].forEach(jobData => {
              jobs.push(this.addJob(jobData));
            });
          }
          if (resolveWResponse) {
            return jobsResp;
          }
          return jobs;
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

    addJob: function(jobData) {
      const jobs = this.getJobs();
      const jobFound = jobs.find(job => job.getProjectUuid() === jobData["projectUuid"]);
      if (jobFound) {
        return jobFound;
      }
      const job = new osparc.data.Job(jobData);
      jobs.push(job);
      this.fireDataEvent("changeJobs");
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
