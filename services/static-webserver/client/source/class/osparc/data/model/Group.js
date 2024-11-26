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
      groupMembers: {},
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

  events: {
    "memberAdded": "qx.event.type.Event",
    "memberRemoved": "qx.event.type.Event",
  },

  statics: {
    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Group));
    }
  },

  members: {
    getGroupMemberByUserId: function(userId) {
      return Object.values(this.getGroupMembers()).find(user => user.getUserId() === userId);
    },

    getGroupMemberByLogin: function(userEmail) {
      return Object.values(this.getGroupMembers()).find(user => user.getLogin() === userEmail);
    },

    addGroupMember: function(user) {
      this.getGroupMembers()[user.getGroupId()] = user;
      this.fireEvent("memberAdded");
    },

    removeGroupMember: function(userId) {
      const groupMember = this.getGroupMemberByUserId(userId);
      if (groupMember) {
        delete this.getGroupMembers()[groupMember.getGroupId()];
        this.fireEvent("memberRemoved");
      }
    },

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
