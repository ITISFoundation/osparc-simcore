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
 * Class that stores Tag data.
 */

qx.Class.define("osparc.data.model.Tag", {
  extend: qx.core.Object,

  /**
   * @param tagData {Object} Object containing the serialized Tag Data
   */
  construct: function(tagData) {
    this.base(arguments);

    this.set({
      tagId: tagData.id,
      name: tagData.name,
      description: tagData.description,
      color: tagData.color,
      accessRights: tagData.accessRights,
    });
  },

  properties: {
    tagId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeTagId"
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

    color: {
      check: "Color",
      event: "changeColor",
      init: "#303030"
    },

    accessRights: {
      check: "Object",
      nullable: false,
      init: null,
      event: "changeAccessRights"
    },
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
