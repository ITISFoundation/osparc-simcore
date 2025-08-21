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

    stateReceived: function(state) {
      if (state) {
        this.set({
          currentUserGroupIds: state.currentUserGroupIds || [],
          locked: state.locked || false,
          status: state.status || "NOT_STARTED",
        });
      }
    },
  }
});
