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

qx.Class.define("osparc.workbench.Annotation", {
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
      id = osparc.utils.Utils.uuidV4();
    }
    let color = "color" in data ? data.color : this.getColor();
    if (color && color[0] !== "#") {
      color = osparc.utils.Utils.namedColorToHex(color);
    }
    this.set({
      id,
      type: data.type,
      color,
      attributes: data.attributes
    });
  },

  statics: {
    DEFAULT_COLOR: "#FFFF01"
  },

  properties: {
    id: {
      check: "String",
      nullable: false
    },

    type: {
      check: ["note", "rect", "text"],
      nullable: false
    },

    color: {
      check: "Color",
      event: "changeColor",
      init: "#FFFF01",
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
    "annotationClicked": "qx.event.type.Data",
    "annotationStartedMoving": "qx.event.type.Event",
    "annotationMoving": "qx.event.type.Event",
    "annotationStoppedMoving": "qx.event.type.Event"
  },

  members: {
    __svgLayer: null,

    __drawAnnotation: async function(attrs) {
      if (this.__svgLayer === null) {
        return;
      }

      let representation = null;
      switch (this.getType()) {
        case "note": {
          const user = osparc.store.Groups.getInstance().getUserByGroupId(attrs.recipientGid);
          representation = this.__svgLayer.drawAnnotationNote(attrs.x, attrs.y, user ? user.getLabel() : "", attrs.text);
          break;
        }
        case "rect":
          representation = this.__svgLayer.drawAnnotationRect(attrs.width, attrs.height, attrs.x, attrs.y, this.getColor());
          break;
        case "text":
          representation = this.__svgLayer.drawAnnotationText(attrs.x, attrs.y, attrs.text, this.getColor(), attrs.fontSize);
          break;
      }
      if (representation) {
        osparc.wrapper.Svg.makeDraggable(representation);
        representation.node.addEventListener("click", e => {
          this.fireDataEvent("annotationClicked", e.ctrlKey);
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

    getRepresentationPosition: function() {
      const representation = this.getRepresentation();
      if (representation) {
        const attrs = osparc.wrapper.Svg.getRectAttributes(representation);
        return {
          x: parseInt(attrs.x),
          y: parseInt(attrs.y)
        };
      }
      return null;
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

    setFontSize: function(fontSize) {
      this.getAttributes().fontSize = fontSize;
      const representation = this.getRepresentation();
      if (representation) {
        osparc.wrapper.Svg.updateTextSize(representation, fontSize);
      }
    },

    setSelected: function(selected) {
      const representation = this.getRepresentation();
      if (representation) {
        switch (this.getType()) {
          case "rect":
          case "text": {
            if (selected) {
              if (!("bBox" in representation.node)) {
                const bBox = this.__svgLayer.drawBoundingBox(this);
                representation.node["bBox"] = bBox;
              }
            } else if ("bBox" in representation.node) {
              osparc.wrapper.Svg.removeItem(representation.node["bBox"]);
              delete representation.node["bBox"];
            }
            break;
          }
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
