/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Class that stores File data.
 */

qx.Class.define("osparc.data.model.File", {
  extend: qx.core.Object,

  /**
   * @param fileData {Object} Object containing the serialized File Data
   */
  construct: function(fileData) {
    this.base(arguments);

    this.set({
      name: fileData.name,
      projectId: fileData.projectId,
      path: fileData.path,
      createdAt: fileData.createdAt ? new Date(fileData.createdAt) : null,
      modifiedAt: fileData.modifiedAt ? new Date(fileData.modifiedAt) : null,
      isDirectory: fileData.isDirectory || false,
      size: fileData.size || null,
    });
  },

  properties: {
    name: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeName"
    },

    projectId: {
      check: "String",
      nullable: false,
      init: null,
      event: "changeProjectId"
    },

    path: {
      check: "String",
      nullable: false,
      init: null,
      event: "changePath"
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

    isDirectory: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeIsDirectory"
    },

    size: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeSize"
    },
  },
});
