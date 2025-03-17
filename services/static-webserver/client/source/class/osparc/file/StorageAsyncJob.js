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

qx.Class.define("osparc.file.StorageAsyncJob", {
  extend: qx.core.Object,

  construct: function(jobId, interval = 1000) {
    this.base(arguments);

    interval ? this.setPollInterval(interval) : this.initPollInterval();

    this.setJobId(jobId);
  },

  events: {
    "resultReceived": "qx.event.type.Data",
    "taskAborted": "qx.event.type.Event",
    "pollingError": "qx.event.type.Data",
  },

  properties: {
    pollInterval: {
      check: "Number",
      nullable: false,
      init: 1000
    },

    jobId: {
      check: "String",
      nullable: false,
      apply: "fetchStatus",
    },
  },

  members: {
    __retries: null,
    __aborting: null,

    fetchStatus: function() {
      const jobId = this.getJobId();
      osparc.data.Resources.fetch("storageAsyncJobs", "jobStatus", { url: { jobId } })
        .then(status => {
          if (this.__aborting) {
            return;
          }
          if (status["done"]) {
            this.__fetchResults();
          } else {
            setTimeout(() => this.fetchStatus(), this.getPollInterval());
          }
        })
        .catch(err => {
          if (this.__retries > 0) {
            this.__retries--;
            this.fetchStatus();
            return;
          }
          this.fireDataEvent("pollingError", err);
        });
    },

    __fetchResults: function() {
      const jobId = this.getJobId();
      osparc.data.Resources.fetch("storageAsyncJobs", "jobResult", { url: { jobId } })
        .then(result => {
          console.log(result);
          this.fireDataEvent("resultReceived", result);
        })
        .catch(err => {
          console.error(err);
          this.fireDataEvent("pollingError", err);
        });
    },

    abortRequested: function() {
      this.__aborting = true;
      const jobId = this.getJobId();
      osparc.data.Resources.fetch("storageAsyncJobs", "result", { url: { jobId } })
        .then(() => this.fireEvent("taskAborted"))
        .catch(err => {
          throw err;
        });
    }
  }
});
