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

    let description = "";
    if (userData["first_name"]) {
      description = userData["first_name"];
      if (userData["last_name"]) {
        description += " " + userData["last_name"];
      }
      description += " - ";
    }
    if (userData["login"]) {
      description += userData["login"];
    }
    const thumbnail = osparc.utils.Avatar.emailToThumbnail(userData["login"], userData["userName"]);
    this.set({
      userId: parseInt(userData["id"]),
      groupId: parseInt(userData["gid"]),
      username: userData["userName"],
      firstName: userData["first_name"],
      lastName: userData["last_name"],
      email: userData["login"],
      label: userData["userName"],
      description,
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

    description: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeDescription",
    },

    username: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeUsername",
    },

    firstName: {
      check: "String",
      nullable: true,
      init: "",
      event: "changeFirstName"
    },

    lastName: {
      check: "String",
      nullable: true,
      init: "",
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
