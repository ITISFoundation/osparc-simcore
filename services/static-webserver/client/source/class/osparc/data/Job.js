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
});
