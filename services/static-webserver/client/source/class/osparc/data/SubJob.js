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

  construct: function(subJobData) {
    this.base(arguments);

    this.set({
      projectUuid: subJobData["projectUuid"],
      nodeId: subJobData["nodeId"],
      nodeName: subJobData["nodeId"],
      state: subJobData["state"],
      progress: subJobData["progress"],
      startedAt: subJobData["startedAt"] ? new Date(subJobData["startedAt"]) : null,
      endedAt: subJobData["endedAt"] ? new Date(subJobData["endedAt"]) : null,
      image: subJobData["image"] || {},
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

  members: {
    updateSubJob: function(subJobData) {
      this.set({
        state: subJobData["state"],
        progress: subJobData["progress"],
        startedAt: subJobData["startedAt"] ? new Date(subJobData["startedAt"]) : null,
        endedAt: subJobData["endedAt"] ? new Date(subJobData["endedAt"]) : null,
      });
    },
  },
});
