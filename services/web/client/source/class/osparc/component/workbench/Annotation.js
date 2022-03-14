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
    * @param data {Object} data containing type, color, attributes and (optional) id
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
      color: "color" in data ? data.color : this.getColor(),
      attributes: data.attributes
    });
  },

  statics: {
    DEFAULT_COLOR: "#007fd4" // Visual Studio blue
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

    color: {
      check: "Color",
      event: "changeColor",
      init: "#007fd4",
      apply: "__applyColor"
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

  events: {
    "annotationClicked": "qx.event.type.Event",
    "annotationStartedMoving": "qx.event.type.Event",
    "annotationMoving": "qx.event.type.Event",
    "annotationStoppedMoving": "qx.event.type.Event"
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
          representation = this.__svgLayer.drawAnnotationRect(attrs.width, attrs.height, attrs.x, attrs.y, this.getColor());
          break;
        case "text":
          representation = this.__svgLayer.drawAnnotationText(attrs.width, attrs.height, attrs.x, attrs.y, attrs.text, this.getColor());
          break;
      }
      if (representation) {
        osparc.wrapper.Svg.makeDraggable(representation);
        representation.node.addEventListener("click", e => {
          this.fireEvent("annotationClicked");
          e.stopPropagation();
        }, this);
        representation.on("dragstart", () => this.fireEvent("annotationStartedMoving"));
        representation.on("dragmove", () => this.fireEvent("annotationMoving"));
        representation.on("dragend", () => this.fireEvent("annotationStoppedMoving"));
        this.setRepresentation(representation);
      }
    },

    __applyColor: function(color) {
      const representation = this.getRepresentation();
      if (representation) {
        switch (this.getType()) {
          case "rect":
            osparc.wrapper.Svg.updateItemColor(representation, color);
            break;
          case "text":
            osparc.wrapper.Svg.updateTextColor(representation, color);
            break;
        }
      }
    },

    getPosition: function() {
      const attrs = this.getAttributes();
      if (attrs) {
        return {
          x: parseInt(attrs.x),
          y: parseInt(attrs.y)
        };
      }
      return null;
    },

    setPosition: function(x, y) {
      const representation = this.getRepresentation();
      if (representation) {
        x = parseInt(x) < 0 ? 0 : parseInt(x);
        y = parseInt(y) < 0 ? 0 : parseInt(y);
        osparc.wrapper.Svg.updateItemPos(representation, x, y);
        this.getAttributes().x = x;
        this.getAttributes().y = y;
      }
    },

    setText: function(newText) {
      this.getAttributes().text = newText;
      const representation = this.getRepresentation();
      if (representation) {
        osparc.wrapper.Svg.updateText(representation, newText);
      }
    },

    setSelected: function(selected) {
      const representation = this.getRepresentation();
      if (representation) {
        switch (this.getType()) {
          case "rect":
            osparc.wrapper.Svg.updateItemColor(representation, selected ? "yellow" : this.getColor());
            break;
          case "text":
            osparc.wrapper.Svg.updateTextColor(representation, selected ? "yellow" : this.getColor());
            break;
        }
      }
    },

    serialize: function() {
      return {
        type: this.getType(),
        attributes: this.getAttributes(),
        color: this.getColor()
      };
    }
  }
});
