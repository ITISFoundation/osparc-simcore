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
 * Class that stores Service data.
 */

qx.Class.define("osparc.data.model.Folder", {
  extend: qx.core.Object,

  /**
   * @param folderData {Object} Object containing the serialized Folder Data
   */
  construct: function(folderData) {
    this.base(arguments);

    this.set({
      id: folderData.id,
      parentId: folderData.parentFolderId,
      name: folderData.name,
      description: folderData.description,
      myAccessRights: folderData.myAccessRights,
      accessRights: folderData.accessRights,
      createdAt: new Date(folderData.createdAt),
      lastModified: new Date(folderData.lastModified),
    });
  },

  properties: {
    id: {
      check: "Number",
      nullable: false,
      init: null,
      event: "changeId"
    },

    parentId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeParentId"
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
    patchFolder: function(folderId, propKey, value) {
      return osparc.store.Folders.getInstance().patchFolder(folderId, propKey, value);
    },

    getProperties: function() {
      return Object.keys(qx.util.PropertyUtil.getProperties(osparc.data.model.Folder));
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
