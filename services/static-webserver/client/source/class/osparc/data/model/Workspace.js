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
 * Class that stores Workspace data.
 */

qx.Class.define("osparc.data.model.Workspace", {
  extend: qx.core.Object,

  /**
   * @param workspaceData {Object} Object containing the serialized Workspace Data
   */
  construct: function(workspaceData) {
    this.base(arguments);

    this.set({
      workspaceId: workspaceData.workspaceId,
      name: workspaceData.name,
      description: workspaceData.description,
      thumbnail: workspaceData.thumbnail,
      myAccessRights: workspaceData.myAccessRights,
      accessRights: workspaceData.accessRights,
      createdAt: new Date(workspaceData.createdAt),
      modifiedAt: new Date(workspaceData.modifiedAt),
      trashedAt: workspaceData.trashedAt ? new Date(workspaceData.trashedAt) : null,
      trashedBy: workspaceData.trashedBy,
    });
  },

  properties: {
    workspaceId: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeId"
    },

    name: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeName"
    },

    description: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeDescription"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeThumbnail"
    },

    myAccessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeMyAccessRights"
    },

    accessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeAccessRights"
    },

    createdAt: {
      check: "Date",
      nullable: true,
      init: null,
      event: "changeCreatedAt"
    },

    modifiedAt: {
      check: "Date",
      nullable: true,
      init: null,
      event: "changeModifiedAt"
    },

    trashedAt: {
      check: "Date",
      nullable: true,
      init: null,
    },

    trashedBy: {
      check: "Number",
      nullable: true,
      init: null,
    },
  },

  statics: {
    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Workspace));
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
