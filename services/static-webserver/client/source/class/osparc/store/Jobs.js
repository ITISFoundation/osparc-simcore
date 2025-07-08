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

  statics: {
    SERVER_MAX_LIMIT: 49,
  },

  members: {
    fetchJobsLatest: function(
      runningOnly = true,
      offset = 0,
      limit = this.self().SERVER_MAX_LIMIT,
      orderBy = {
        field: "submitted_at",
        direction: "desc"
      },
      filters = null,
      resolveWResponse = false
    ) {
      const params = {
        url: {
          runningOnly,
          offset,
          limit,
          orderBy: JSON.stringify(orderBy),
          filters: JSON.stringify(filters ? filters : {}),
        }
      };
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("runs", "getPageLatest", params, options)
        .then(jobsResp => {
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

    fetchJobsHistory: function(
      projectId,
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
          projectId,
          offset,
          limit,
          orderBy: JSON.stringify(orderBy),
        }
      };
      const options = {
        resolveWResponse: true
      };
      return osparc.data.Resources.fetch("runs", "getPageHistory", params, options)
        .then(jobsResp => {
          if (resolveWResponse) {
            return jobsResp;
          }
          const jobs = [];
          if ("data" in jobsResp) {
            jobsResp["data"].forEach(jobData => {
              const job = new osparc.data.Job(jobData);
              jobs.push(job);
            });
          }
          return jobs;
        })
        .catch(err => console.error(err));
    },

    fetchSubJobs: function(
      collectionRunId,
      orderBy = {
        field: "started_at",
        direction: "desc"
      },
    ) {
      const params = {
        url: {
          collectionRunId,
          orderBy: JSON.stringify(orderBy),
        }
      };
      return osparc.data.Resources.getInstance().getAllPages("subRuns", params, "getPageLatest")
        .then(subJobsData => {
          const subJobs = [];
          subJobsData.forEach(subJobData => {
            subJobs.push(this.addSubJob(collectionRunId, subJobData));
          });
          return subJobs;
        })
        .catch(err => console.error(err));
    },

    __addJob: function(jobData) {
      const jobs = this.getJobs();
      const jobFound = jobs.find(job => job.getCollectionRunId() === jobData["collectionRunId"]);
      if (jobFound) {
        jobFound.updateJob(jobData);
        return jobFound;
      }
      const job = new osparc.data.Job(jobData);
      jobs.push(job);
      return job;
    },

    addSubJob: function(collectionRunId, subJobData) {
      let job = this.getJob(collectionRunId);
      if (!job) {
        const jobs = this.getJobs();
        job = new osparc.data.Job({
          collectionRunId,
        });
        jobs.push(job);
      }
      const subJob = job.addSubJob(collectionRunId, subJobData);
      return subJob;
    },

    getJob: function(collectionRunId) {
      const jobs = this.getJobs();
      return jobs.find(job => job.getCollectionRunId() === collectionRunId);
    },
  }
});
