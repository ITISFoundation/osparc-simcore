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
      lastModified: new Date(workspaceData.lastModified),
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

    lastModified: {
      check: "Date",
      nullable: true,
      init: null,
      event: "changeLastModified"
    }
  },

  statics: {
    putWorkspace: function(workspaceId, propKey, value) {
      return osparc.store.Workspaces.putWorkspace(workspaceId, propKey, value);
    },

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
