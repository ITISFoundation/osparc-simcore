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

qx.Class.define("osparc.data.model.Service", {
  extend: qx.core.Object,

  /**
   * @param serviceData {Object} Object containing the serialized Study Data
   */
  construct: function(serviceData) {
    this.base(arguments);

    this.set({
      key: serviceData.key,
      name: serviceData.name,
      description: serviceData.description,
      thumbnail: serviceData.thumbnail,
      owner: serviceData.owner || "",
      accessRights: serviceData.accessRights,
      classifiers: serviceData.classifiers || [],
      quality: serviceData.quality || null,
      hits: serviceData.hits || 0
    });
  },

  properties: {
    key: {
      check: "String",
      nullable: false,
      event: "changeKey",
      init: null
    },

    name: {
      check: "String",
      nullable: false,
      event: "changeName",
      init: null
    },

    description: {
      check: "String",
      nullable: false,
      event: "changeDescription",
      init: null
    },

    owner: {
      check: "String",
      nullable: false,
      event: "changeOwner",
      init: ""
    },

    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAccessRights",
      init: {}
    },

    thumbnail: {
      check: "String",
      nullable: true,
      event: "changeThumbnail",
      init: null
    },

    classifiers: {
      check: "Array",
      init: [],
      event: "changeClassifiers",
      nullable: false
    },

    quality: {
      check: "Object",
      init: {},
      event: "changeQuality",
      nullable: false
    },

    hits: {
      check: "Number",
      init: 0,
      event: "changeHits",
      nullable: false
    }
  }
});
