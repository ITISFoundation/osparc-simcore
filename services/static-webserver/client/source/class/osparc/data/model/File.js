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
      projectId: fileData.projectId || null,
      createdAt: new Date(fileData.createdAt),
      modifiedAt: new Date(fileData.modifiedAt),
      size: fileData.size || null,
      path: fileData.path,
      isDirectory: fileData.isDirectory || false,
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
      nullable: true,
      init: null,
      event: "changeProjectId"
    },

    createdAt: {
      check: "Date",
      nullable: false,
      init: null,
      event: "changeCreatedAt"
    },

    modifiedAt: {
      check: "Date",
      nullable: false,
      init: null,
      event: "changeModifiedAt"
    },

    size: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeSize"
    },

    path: {
      check: "String",
      nullable: false,
      init: null,
      event: "changePath"
    },

    isDirectory: {
      check: "Boolean",
      nullable: false,
      init: false,
      event: "changeIsDirectory"
    },
  },
});
