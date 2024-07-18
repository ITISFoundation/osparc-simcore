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
      name: folderData.name,
      description: folderData.description,
      accessRights: folderData.accessRights,
      sharedAccessRights: folderData.sharedAccessRights,
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

    accessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeAccessRights"
    },

    sharedAccessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeSharedAccessRights"
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
