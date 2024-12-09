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
 * Class that stores User data + access rights to the resource.
 */

qx.Class.define("osparc.data.model.UserMember", {
  extend: osparc.data.model.User,

  /**
   * @param userData {Object} Object containing the serialized User Data
   */
  construct: function(userData) {
    this.base(arguments, userData);

    this.set({
      accessRights: userData["accessRights"],
    });
  },

  properties: {
    accessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeAccessRights",
    },
  },
});
