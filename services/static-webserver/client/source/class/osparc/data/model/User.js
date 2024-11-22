/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores User data.
 */

qx.Class.define("osparc.data.model.User", {
  extend: qx.core.Object,

  /**
   * @param userData {Object} Object containing the serialized User Data
   */
  construct: function(userData) {
    this.base(arguments);

    let label = userData["login"];
    if ("first_name" in userData && userData["first_name"]) {
      label = osparc.utils.Utils.firstsUp(userData["first_name"]);
      if (userData["last_name"]) {
        label += " " + osparc.utils.Utils.firstsUp(userData["last_name"]);
      }
    }
    this.set({
      userId: userData.id,
      groupId: userData.gid,
      label: label,
      login: userData.login,
      thumbnail: this.self().emailToThumbnail(userData.login),
      accessRights: userData.accessRights,
    });
  },

  properties: {
    userId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeUserId",
    },

    groupId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeGroupId",
    },

    label: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeLabel",
    },

    login: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeLogin",
    },

    accessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeAccessRights",
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: "",
      event: "changeThumbnail",
    },
  },

  statics: {
    emailToThumbnail: function(email) {
      return osparc.utils.Avatar.getUrl(email, 32)
    },
  }
});
