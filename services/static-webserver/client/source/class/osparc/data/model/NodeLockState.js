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

qx.Class.define("osparc.data.model.NodeLockState", {
  extend: qx.core.Object,

  construct: function(lockState) {
    this.base(arguments);

    this.set({
      currentUserGroupIds: lockState["current_user_groupids"] || [],
      locked: lockState["locked"] || false,
      status: lockState["status"] || "NOT_STARTED",
    });
  },

  properties: {
    currentUserGroupIds: {
      check: "Array",
      init: [],
      nullable: false,
      apply: "__currentUserGroupIds",
    },

    locked: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeLocked",
    },

    status: {
      check: ["NOT_STARTED", "STARTED", "OPENED"],
      init: false,
      nullable: false,
      event: "changeStatus",
    }
  },

  members: {
    __currentUserGroupIds: function(currentUserGroupIds) {
      console.log(currentUserGroupIds);
    },
  }
});
