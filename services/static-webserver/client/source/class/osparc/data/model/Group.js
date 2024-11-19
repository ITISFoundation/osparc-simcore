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
      workspaceId: groupData.workspaceId,
      groupId: groupData.groupId,
      parentGroupId: groupData.parentGroupId,
      name: groupData.name,
      myAccessRights: groupData.myAccessRights,
      owner: groupData.owner,
      createdAt: new Date(groupData.createdAt),
      lastModified: new Date(groupData.modifiedAt),
      trashedAt: groupData.trashedAt ? new Date(groupData.trashedAt) : this.getTrashedAt(),
    });
  },

  properties: {
    workspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeWorkspaceId"
    },

    groupId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeGroupId"
    },

    parentGroupId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeParentGroupId"
    },

    name: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeName"
    },

    myAccessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeMyAccessRights"
    },

    owner: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeOwner"
    },

    createdAt: {
      check: "Date",
      nullable: true,
      init: null,
      event: "changeCreatedAt"
    },

    lastModified: {
      check: "Date",
      nullable: true,
      init: null,
      event: "changeLastModified"
    },

    trashedAt: {
      check: "Date",
      nullable: true,
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
