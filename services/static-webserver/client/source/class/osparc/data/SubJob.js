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

qx.Class.define("osparc.data.SubJob", {
  extend: qx.core.Object,

  construct: function(jobData) {
    this.base(arguments);

    this.set({
      projectUuid: jobData["projectUuid"],
      nodeId: jobData["nodeId"],
      nodeName: jobData["nodeId"],
      state: jobData["state"],
      progress: jobData["progress"],
      startedAt: jobData["startedAt"] ? new Date(jobData["startedAt"]) : null,
      endedAt: jobData["endedAt"] ? new Date(jobData["endedAt"]) : null,
      image: jobData["image"] || {},
    });
  },

  properties: {
    projectUuid: {
      check: "String",
      nullable: false,
      init: null,
    },

    nodeId: {
      check: "String",
      nullable: false,
      init: null,
    },

    nodeName: {
      check: "String",
      nullable: false,
      init: null,
    },

    state: {
      check: "String",
      nullable: true,
      init: null,
    },

    progress: {
      check: "Number",
      nullable: true,
      init: null,
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

    image: {
      check: "Object",
      nullable: false,
      init: null,
    },
  },
});
