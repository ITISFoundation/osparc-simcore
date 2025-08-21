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

  construct: function() {
    this.base(arguments);

    this.initCurrentUserGroupIds();
    this.initLocked();
    this.initStatus();
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
      // check: ["NOT_STARTED", "STARTED", "OPENED"],
      check: "String",
      init: false,
      nullable: false,
      event: "changeStatus",
    }
  },

  members: {
    stateReceived: function(state) {
      if (state) {
        this.set({
          currentUserGroupIds: "current_user_groupids" in state ? state["current_user_groupids"] : [],
          locked: "locked" in state ? state["locked"] : false,
          status: "status" in state ? state["status"] : "NOT_STARTED",
        });
      }
    },

    __currentUserGroupIds: function(currentUserGroupIds) {
      console.log("currentUserGroupIds", currentUserGroupIds);
    },
  }
});
