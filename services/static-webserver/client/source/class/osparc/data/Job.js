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
      projectUuid: jobData["projectUuid"],
      state: jobData["state"],
      submittedAt: jobData["submittedAt"] ? new Date(jobData["submittedAt"]) : null,
      startedAt: jobData["startedAt"] ? new Date(jobData["startedAt"]) : null,
      endedAt: jobData["endedAt"] ? new Date(jobData["endedAt"]) : null,
      info: jobData["info"] || null,
    });

    if (jobData["info"] && jobData["info"]["project_name"]) {
      this.setProjectName(jobData["info"]["project_name"]);
    }

    this.__subJobs = [];
  },

  properties: {
    projectUuid: {
      check: "String",
      nullable: false,
      init: null,
    },

    projectName: {
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
      nullable: false,
      init: null,
    },
  },

  members: {
    __subJobs: null,

    addSubJob: function(subJobData) {
      const subJobFound = this.__subJobs.find(subJb => subJb.getNodeId() === subJobData["nodeId"]);
      if (subJobFound) {
        subJobFound.updateSubJob(subJobData);
        return subJobFound;
      }

      const subJob = new osparc.data.SubJob(subJobData);
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
