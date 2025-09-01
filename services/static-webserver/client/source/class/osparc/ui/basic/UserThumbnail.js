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

qx.Class.define("osparc.ui.basic.UserThumbnail", {
  extend: qx.ui.basic.Image,

  construct: function(size) {
    this.base(arguments);

    this.set(osparc.utils.Utils.getThumbnailProps(size));

    if (osparc.data.Permissions.getInstance().isProductOwner()) {
      this.setCursor("pointer");
      this.addListener("tap", this.__openUserDetails, this);
    }
  },

  properties: {
    user: {
      check: "osparc.data.model.User",
      init: true,
      nullable: true,
      apply: "__applyUser",
    }
  },

  members: {
    __openUserDetails: function() {
      if (this.getUser()) {
        osparc.user.UserDetails.popUpInWindow(this.getUser());
      }
    },
  }
});
