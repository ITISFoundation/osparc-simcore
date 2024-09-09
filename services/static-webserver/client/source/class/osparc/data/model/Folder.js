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
 * Class that stores Folder data.
 */

qx.Class.define("osparc.data.model.Folder", {
  extend: qx.core.Object,

  /**
   * @param folderData {Object} Object containing the serialized Folder Data
   */
  construct: function(folderData) {
    this.base(arguments);

    this.set({
      folderId: folderData.folderId,
      parentId: folderData.parentFolderId,
      name: folderData.name,
      myAccessRights: folderData.myAccessRights,
      owner: folderData.owner,
      createdAt: new Date(folderData.createdAt),
      lastModified: new Date(folderData.modifiedAt),
    });
  },

  properties: {
    folderId: {
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
    }
  },

  statics: {
    putFolder: function(folderId, propKey, value) {
      return osparc.store.Folders.getInstance().putFolder(folderId, propKey, value);
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
