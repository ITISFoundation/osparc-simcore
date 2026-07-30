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

qx.Class.define("osparc.data.Job", {
  extend: qx.core.Object,

  construct: function(jobData) {
    this.base(arguments);

    this.set({
      collectionRunId: jobData["collectionRunId"],
      projectIds: jobData["projectIds"],
      name: jobData["name"] || "",
      state: jobData["state"] || "UNKNOWN",
      submittedAt: jobData["submittedAt"] ? new Date(jobData["submittedAt"]) : null,
      startedAt: jobData["startedAt"] ? new Date(jobData["startedAt"]) : null,
      endedAt: jobData["endedAt"] ? new Date(jobData["endedAt"]) : null,
      info: jobData["info"] || null,
    });

    this.__subJobs = [];
  },

  properties: {
    collectionRunId: {
      check: "String",
      nullable: false,
      init: null,
    },

    projectIds: {
      check: "Array",
      nullable: false,
      init: null,
    },

    name: {
      check: "String",
      nullable: false,
      init: null,
    },

    state: {
      check: "String",
      nullable: false,
      init: null,
    },

    submittedAt: {
      check: "Date",
      init: null,
      nullable: true,
    },

    startedAt: {
      check: "Date",
      init: null,
      nullable: true,
    },

    endedAt: {
      check: "Date",
      init: null,
      nullable: true,
    },

    info: {
      check: "Object",
      nullable: true,
      init: null,
    },
  },

  statics: {
    STATUS_LABELS: {
      "UNKNOWN": qx.locale.Manager.tr("Unknown"),
      "NOT_STARTED": qx.locale.Manager.tr("Unknown"),
      "PUBLISHED": qx.locale.Manager.tr("Queued"),
      "PENDING": qx.locale.Manager.tr("Queued"),
      "RUNNING": qx.locale.Manager.tr("Running"),
      "STARTED": qx.locale.Manager.tr("Running"),
      "SUCCESS": qx.locale.Manager.tr("Finished"),
      "FAILED": qx.locale.Manager.tr("Failed"),
      "ABORTED": qx.locale.Manager.tr("Aborted"),
      "WAITING_FOR_RESOURCES": qx.locale.Manager.tr("Hardware is ready, installing solvers"),
      "WAITING_FOR_CLUSTER": qx.locale.Manager.tr("Creating your personal computing hardware"),
    },
  },

  members: {
    __subJobs: null,

    addSubJob: function(collectionRunId, subJobData) {
      const subJobFound = this.__subJobs.find(subJb => subJb.getNodeId() === subJobData["nodeId"]);
      if (subJobFound) {
        subJobFound.updateSubJob(subJobData);
        return subJobFound;
      }

      const subJob = new osparc.data.SubJob(collectionRunId, subJobData);
      this.__subJobs.push(subJob);
      return subJob;
    },

    updateJob: function(jobData) {
      this.set({
        state: jobData["state"],
        submittedAt: jobData["submittedAt"] ? new Date(jobData["submittedAt"]) : null,
        startedAt: jobData["startedAt"] ? new Date(jobData["startedAt"]) : null,
        endedAt: jobData["endedAt"] ? new Date(jobData["endedAt"]) : null,
      });
    },

    getSubJobs: function() {
      return this.__subJobs;
    },

    getSubJob: function(nodeId) {
      return this.__subJobs.find(subJb => subJb.getNodeId() === nodeId);
    },
  }
});
