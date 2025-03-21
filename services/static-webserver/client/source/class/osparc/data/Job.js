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
      jobId: jobData["job_id"],
      solver: jobData["solver"],
      status: jobData["status"],
      progress: jobData["progress"],
      submittedAt: jobData["submitted_at"] ? new Date(jobData["submitted_at"]) : null,
      startedAt: jobData["started_at"] ? new Date(jobData["started_at"]) : null,
      instance: jobData["instance"],
    });
  },

  properties: {
    jobId: {
      check: "String",
      nullable: false,
      init: null,
    },

    solver: {
      check: "String",
      nullable: false,
      init: null,
    },

    status: {
      check: "String",
      nullable: false,
      init: null,
    },

    progress: {
      check: "Number",
      init: null,
      nullable: true,
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

    instance: {
      check: "String",
      nullable: false,
      init: null,
    },

    info: {
      check: "Object",
      nullable: false,
      init: null,
    },
  },
});
