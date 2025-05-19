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
      const usersRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "users-data");
      pendingUsersContainer.add(usersRespViewer);
    }
  }
});
