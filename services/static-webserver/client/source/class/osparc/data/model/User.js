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

    const userId = ("id" in userData) ? parseInt(userData["id"]) : parseInt(userData["userId"]);
    const groupId = ("gid" in userData) ? parseInt(userData["gid"]) : parseInt(userData["groupId"]);
    const username = userData["userName"];
    const email = ("login" in userData) ? userData["login"] : userData["email"];
    let firstName = "";
    if (userData["first_name"]) {
      firstName = userData["first_name"];
    } else if (userData["firstName"]) {
      firstName = userData["firstName"];
    }
    let lastName = "";
    if (userData["last_name"]) {
      lastName = userData["last_name"];
    } else if (userData["lastName"]) {
      lastName = userData["lastName"];
    }
    let description = [firstName, lastName].join(" ").trim(); // the null values will be replaced by empty strings
    if (email) {
      if (description) {
        description += " - "
      }
      description += email;
    }
    const thumbnail = osparc.utils.Avatar.emailToThumbnail(email, username);
    this.set({
      userId,
      groupId,
      username,
      firstName,
      lastName,
      email,
      thumbnail,
      label: username,
      description,
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
