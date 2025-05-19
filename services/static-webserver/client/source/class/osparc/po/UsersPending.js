/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo-Valero (pcrespov)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.UsersPending", {
  extend: osparc.po.BaseView,

  statics: {
    getPendingUsers: function() {
      return new Promise(resolve => {
        resolve({
          data: [{
            name: "John Doe",
            email: "john.doe@email.com",
            status: "APPROVAL_PENDING",
            date: "2025-01-01 00:00:00.702394",
          }, {
            name: "Jane Doe",
            email: "jane.doe@email.com",
            status: "APPROVAL_DENIED",
            date: "2025-01-01 00:01:00.702394",
          }, {
            name: "Alice Smith",
            email: "alice.smith@email.com",
            status: "CONFIRMATION_PENDING",
            date: "2025-01-01 00:02:00.702394",
          }]
        });
      });
    },
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "pending-users-container":
          control = new qx.ui.container.Scroll();
          this._add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("pending-users-container");

      this.__populatePendingUsersLayout();
    },

    __populatePendingUsersLayout: function(respData) {
      const pendingUsersContainer = this.getChildControl("pending-users-container");
      osparc.utils.Utils.removeAllChildren(pendingUsersContainer);

      // osparc.data.Resources.fetch("poUsers", "getPendingUsers", params)
      this.self().getPendingUsers()
        .then(pendingUsers => {
          console.log("Pending users: ", pendingUsers);
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    }
  }
});
