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
    },
  },

  events: {
    "changeJobsActive": "qx.event.type.Data",
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
      return osparc.data.Resources.fetch("jobsActive", "getPageLatest", params, options)
        .then(jobsResp => {
          this.fireDataEvent("changeJobsActive", jobsResp["_meta"]["total"]);
          const jobsActive = [];
          if ("data" in jobsResp) {
            jobsResp["data"].forEach(jobActiveData => {
              jobsActive.push(this.__addJob(jobActiveData));
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
      return osparc.data.Resources.getInstance().getAllPages("subJobs", params, "getPageLatest")
        .then(subJobsData => {
          const subJobs = [];
          subJobsData.forEach(subJobData => {
            subJobs.push(this.addSubJob(subJobData));
          });
          return subJobs;
        })
        .catch(err => console.error(err));
    },

    __addJob: function(jobData) {
      const jobs = this.getJobs();
      const jobFound = jobs.find(job => job.getProjectUuid() === jobData["projectUuid"]);
      if (jobFound) {
        jobFound.updateJob(jobData);
        return jobFound;
      }
      const job = new osparc.data.Job(jobData);
      jobs.push(job);
      return job;
    },

    addSubJob: function(subJobData) {
      let job = this.getJob(subJobData["projectUuid"]);
      if (!job) {
        const jobs = this.getJobs();
        job = new osparc.data.Job({
          "projectUuid": subJobData["projectUuid"],
        });
        jobs.push(job);
      }
      const subJob = job.addSubJob(subJobData);
      return subJob;
    },

    getJob: function(projectUuid) {
      const jobs = this.getJobs();
      return jobs.find(job => job.getProjectUuid() === projectUuid);
    },
  }
});
