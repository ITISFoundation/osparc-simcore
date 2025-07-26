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
   * @param serviceData {Object} Object containing the serialized Service Data
   */
  construct: function(serviceData) {
    this.base(arguments);

    this.set({
      key: serviceData.key,
      version: serviceData.version,
      versionDisplay: serviceData.versionDisplay,
      name: serviceData.name,
      description: serviceData.description,
      thumbnail: serviceData.thumbnail,
      serviceType: serviceData.type,
      contact: serviceData.contact,
      authors: serviceData.authors,
      owner: serviceData.owner || "",
      accessRights: serviceData.accessRights,
      bootOptions: serviceData.bootOptions,
      classifiers: serviceData.classifiers || [],
      quality: serviceData.quality || null,
      xType: serviceData.xType || null,
      hits: serviceData.hits || 0,
    });
  },

  properties: {
    key: {
      check: "String",
      nullable: false,
      event: "changeKey",
      init: null
    },

    version: {
      check: "String",
      nullable: false,
      event: "changeVersion",
      init: null
    },

    versionDisplay: {
      check: "String",
      nullable: true,
      event: "changeVersionDisplay",
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
      nullable: true,
      event: "changeDescription",
      init: null
    },

    thumbnail: {
      check: "String",
      nullable: true,
      event: "changeThumbnail",
      init: null
    },

    serviceType: {
      check: "String",
      nullable: true,
      event: "changeServiceType",
      init: ""
    },

    contact: {
      check: "String",
      nullable: true,
      event: "changeContact",
      init: ""
    },

    authors: {
      check: "Object",
      nullable: true,
      event: "changeAuthors",
      init: {}
    },

    owner: {
      check: "String",
      nullable: true,
      event: "changeOwner",
      init: ""
    },

    accessRights: {
      check: "Object",
      nullable: false,
      event: "changeAccessRights",
      init: {}
    },

    bootOptions: {
      check: "Object",
      init: {},
      event: "changeBootOptions",
      nullable: true
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

    xType: {
      check: "String",
      nullable: true,
      init: null,
      event: "changeXType",
    },

    hits: {
      check: "Number",
      init: 0,
      event: "changeHits",
      nullable: false
    },
  },
});
