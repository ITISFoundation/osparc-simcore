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

    const label = this.self().namesToLabel(userData["first_name"], userData["last_name"]) || userData["login"];
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
    namesToLabel: function(firstName, lastName) {
      let label = "";
      if (firstName) {
        label = osparc.utils.Utils.firstsUp(firstName);
        if (lastName) {
          label += " " + osparc.utils.Utils.firstsUp(lastName);
        }
      }
      return label;
    },

    emailToThumbnail: function(email) {
      return osparc.utils.Avatar.getUrl(email, 32)
    },
  }
});
