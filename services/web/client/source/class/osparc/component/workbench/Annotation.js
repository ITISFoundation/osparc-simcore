/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.workbench.Annotation", {
  extend: qx.core.Object,

  /**
    * @param svgLayer {Object} SVG canvas
    * @param data {Object} data containing type, attributes and (optional) id
    * @param id {String} data
    */
  construct: function(svgLayer, data, id) {
    this.base();

    if (svgLayer) {
      this.__svgLayer = svgLayer;
    }

    if (id === undefined) {
      id = osparc.utils.Utils.uuidv4();
    }
    this.set({
      id,
      type: data.type,
      attributes: data.attributes
    });
  },

  properties: {
    id: {
      check: "String",
      nullable: false
    },

    type: {
      check: ["rect", "text"],
      nullable: false
    },

    attributes: {
      check: "Object",
      nullable: false,
      apply: "__drawAnnotation"
    },

    representation: {
      init: null
    }
  },

  members: {
    __svgLayer: null,

    __drawAnnotation: function(attrs) {
      if (this.__svgLayer === null) {
        return;
      }

      let representation = null;
      switch (this.getType()) {
        case "rect":
          representation = this.__svgLayer.drawAnnotationRect(attrs.width, attrs.height, attrs.x, attrs.y);
          break;
      }
      if (representation) {
        this.setRepresentation(representation);
      }
    },

    serialize: function() {
      return {
        type: this.getType(),
        attributes: this.getAttributes()
      };
    }
  }
});
