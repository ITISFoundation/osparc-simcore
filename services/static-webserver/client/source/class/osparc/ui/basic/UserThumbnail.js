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

    if (osparc.store.Groups.getInstance().amIASupportUser()) {
      this.setCursor("pointer");
      this.addListener("tap", this.__openUserDetails, this);
    }
  },

  properties: {
    user: {
      check: "osparc.data.model.User",
      init: null,
      nullable: true,
      apply: "__applyUser",
    }
  },

  members: {
    __applyUser: function(user) {
      if (user) {
        this.setSource(user.getThumbnail());
      } else {
        this.setSource(osparc.utils.Avatar.emailToThumbnail());
      }
    },

    __openUserDetails: function() {
      if (this.getUser()) {
        osparc.user.UserAccountWindow.openWindow(this.getUser().getGroupId());
      }
    },
  }
});
