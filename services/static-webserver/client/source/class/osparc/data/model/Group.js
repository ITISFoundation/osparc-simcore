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
 * Class that stores Group data.
 */

qx.Class.define("osparc.data.model.Group", {
  extend: qx.core.Object,

  /**
   * @param groupData {Object} Object containing the serialized Group Data
   */
  construct: function(groupData) {
    this.base(arguments);

    this.set({
      groupId: groupData.gid,
      label: groupData.label,
      description: groupData.description,
      accessRights: groupData.accessRights,
      thumbnail: groupData.thumbnail,
    });
  },

  properties: {
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

    groupMembers: {
      check: "Object",
      nullable: true,
      init: null,
      event: "changeGroupMembers",
    },

    groupType: {
      check: ["me", "organization", "productEveryone", "everyone"],
      nullable: false,
      init: null,
    },
  },

  statics: {
    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Group));
    }
  },

  members: {
    serialize: function() {
      const jsonObject = {};
      const propertyKeys = this.self().getProperties();
      propertyKeys.forEach(key => {
        jsonObject[key] = this.get(key);
      });
      return jsonObject;
    }
  }
});
