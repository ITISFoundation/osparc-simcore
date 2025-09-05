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
    const username = userData["userName"] || "-";
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

    this.set({
      userId,
      groupId,
      username,
      firstName,
      lastName,
      email,
      phoneNumber: userData["phone"] || null,
    });

    const description = osparc.data.model.User.userDataToDescription(firstName, lastName, email);
    this.set({
      label: userData["userName"] || description,
      description,
    });

    if (userData["contact"]) {
      const contact = userData["contact"];
      this.set({
        institution: contact["institution"] || null,
        address: contact["address"] || null,
        city: contact["city"] || null,
        state: contact["state"] || null,
        country: contact["country"] || null,
        postalCode: contact["postalCode"] || null,
      });
    }

    // create the thumbnail after setting email and username
    this.set({
      thumbnail: this.createThumbnail(),
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

    phoneNumber: {
      check: "String",
      nullable: true,
      init: null,
      event: "changePhoneNumber"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: "",
      event: "changeThumbnail",
    },

    institution: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeInstitution",
    },

    address: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeAddress",
    },

    city: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeCity",
    },

    state: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeState",
    },

    country: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeCountry",
    },

    postalCode: {
      check: "String",
      nullable: true,
      init: null,
      event: "changePostalCode",
    },
  },

  statics: {
    concatFullName: function(firstName, lastName) {
      return [firstName, lastName].filter(Boolean).join(" ");
    },

    userDataToDescription: function(firstName, lastName, email) {
      let description = this.concatFullName(firstName, lastName);
      if (email) {
        if (description) {
          description += " - "
        }
        description += email;
      }
      return description;
    },
  },

  members: {
    createThumbnail: function(size) {
      return osparc.utils.Avatar.emailToThumbnail(this.getEmail(), this.getUsername(), size);
    },

    getFullName: function() {
      return this.self().concatFullName(this.getFirstName(), this.getLastName());
    },
  },
});
