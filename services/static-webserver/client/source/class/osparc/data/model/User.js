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
    if (userData["first_name"]) {
      label = qx.lang.String.firstUp(userData["first_name"]);
      if (userData["last_name"]) {
        label += " " + qx.lang.String.firstUp(userData["last_name"]);
      }
    }
    const thumbnail = osparc.utils.Avatar.emailToThumbnail(userData["login"]);
    this.set({
      userId: userData["id"],
      groupId: userData["gid"],
      label: label,
      username: userData["username"] || "",
      firstName: userData["first_name"],
      lastName: userData["last_name"],
      email: userData["login"],
      thumbnail,
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

    username: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeUsername",
    },

    firstName: {
      init: "",
      nullable: true,
      check: "String",
      event: "changeFirstName"
    },

    lastName: {
      init: "",
      nullable: true,
      check: "String",
      event: "changeLastName"
    },

    email: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeEmail",
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: "",
      event: "changeThumbnail",
    },
  },
});
