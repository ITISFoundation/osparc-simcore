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
    * @param data {Object} data containing type, color, attributes and (optional) id
    * @param id {String} data
    */
  construct: function(data, id) {
    this.base();

    if (id === undefined) {
      id = osparc.utils.Utils.uuidV4();
    }
    let color = "color" in data ? data.color : this.getColor();
    if (color && color[0] !== "#") {
      color = osparc.utils.Utils.namedColorToHex(color);
    }
    this.set({
      id,
      color,
      attributes: data.attributes,
      type: data.type,
    });
  },

  statics: {
    DEFAULT_COLOR: "#FFFF01",

    TYPES: {
      NOTE: "note",
      RECT: "rect",
      TEXT: "text",
      CONVERSATION: "conversation",
    },
  },

  properties: {
    id: {
      check: "String",
      nullable: false
    },

    type: {
      check: [
        "note", // osparc.workbench.Annotation.TYPES.NOTE
        "rect", // osparc.workbench.Annotation.TYPES.RECT
        "text", // osparc.workbench.Annotation.TYPES.TEXT
        "conversation", // osparc.workbench.Annotation.TYPES.CONVERSATION
      ],
      nullable: false,
    },

    color: {
      check: "Color",
      event: "changeColor",
      init: "#FFFF01",
      nullable: true,
      apply: "__applyColor",
    },

    attributes: {
      check: "Object",
      nullable: false
    },

    svgCanvas: {
      init: null,
      nullable: false,
      apply: "__drawAnnotation",
    },

    representation: {
      init: null
    },
  },

  events: {
    "annotationClicked": "qx.event.type.Data",
    "annotationStartedMoving": "qx.event.type.Event",
    "annotationMoving": "qx.event.type.Event",
    "annotationStoppedMoving": "qx.event.type.Event",
    "annotationChanged": "qx.event.type.Event",
  },

  members: {
    __drawAnnotation: function(svgLayer) {
      if (svgLayer === null) {
        return;
      }

      const attrs = this.getAttributes();
      let representation = null;
      switch (this.getType()) {
        case this.self().TYPES.NOTE: {
          const user = osparc.store.Groups.getInstance().getUserByGroupId(attrs.recipientGid);
          representation = svgLayer.drawAnnotationNote(attrs.x, attrs.y, user ? user.getLabel() : "", attrs.text);
          break;
        }
        case this.self().TYPES.RECT:
          representation = svgLayer.drawAnnotationRect(attrs.width, attrs.height, attrs.x, attrs.y, this.getColor());
          break;
        case this.self().TYPES.TEXT:
          representation = svgLayer.drawAnnotationText(attrs.x, attrs.y, attrs.text, this.getColor(), attrs.fontSize);
          break;
        case this.self().TYPES.CONVERSATION: {
          representation = svgLayer.drawAnnotationConversation(attrs.x, attrs.y, attrs.text);
          const conversationId = attrs.conversationId;
          if (conversationId) {
            osparc.store.ConversationsProject.getInstance().addListener("conversationRenamed", e => {
              const data = e.getData();
              if (conversationId === data["conversationId"]) {
                this.setText(data.name);
              }
            }, this);
          }
          break;
        }
      }

      if (representation) {
        // handle click events
        switch (this.getType()) {
          case this.self().TYPES.NOTE:
          case this.self().TYPES.RECT:
          case this.self().TYPES.TEXT:
            representation.node.addEventListener("click", e => {
              this.fireDataEvent("annotationClicked", e.ctrlKey);
              e.stopPropagation();
            }, this);
            break;
          case this.self().TYPES.CONVERSATION:
            representation["clickables"].forEach(clickable => {
              clickable.click(() => {
                this.fireDataEvent("annotationClicked", false);
              }, this);
            });
            break;
        }

        // handle moving events
        osparc.wrapper.Svg.makeDraggable(representation);
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
          case this.self().TYPES.RECT:
            osparc.wrapper.Svg.updateItemColor(representation, color);
            break;
          case this.self().TYPES.TEXT:
            osparc.wrapper.Svg.updateTextColor(representation, color);
            break;
        }
        this.fireEvent("annotationChanged");
      }
    },

    getRepresentationPosition: function() {
      const representation = this.getRepresentation();
      if (representation) {
        switch (this.getType()) {
          case this.self().TYPES.RECT:
          case this.self().TYPES.TEXT:
          case this.self().TYPES.NOTE: {
            const attrs = osparc.wrapper.Svg.getRectAttributes(representation);
            return {
              x: parseInt(attrs.x),
              y: parseInt(attrs.y),
            };
          }
          case this.self().TYPES.CONVERSATION: {
            const x = representation.transform().x;
            const y = representation.transform().y;
            return {
              x,
              y,
            };
          }
        }
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
      this.fireEvent("annotationChanged");
    },

    setText: function(newText) {
      this.getAttributes().text = newText;
      const representation = this.getRepresentation();
      if (representation) {
        osparc.wrapper.Svg.updateText(representation, newText);
        this.fireEvent("annotationChanged");
      }
    },

    setFontSize: function(fontSize) {
      this.getAttributes().fontSize = fontSize;
      const representation = this.getRepresentation();
      if (representation) {
        osparc.wrapper.Svg.updateTextSize(representation, fontSize);
        this.fireEvent("annotationChanged");
      }
    },

    setSelected: function(selected) {
      const svgCanvas = this.getSvgCanvas();
      if (svgCanvas === null) {
        return;
      };

      const representation = this.getRepresentation();
      if (representation) {
        switch (this.getType()) {
          case this.self().TYPES.RECT:
          case this.self().TYPES.TEXT: {
            if (selected) {
              if (!("bBox" in representation.node)) {
                const bBox = svgCanvas.drawBoundingBox(this);
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
      const serializeData = {
        type: this.getType(),
        attributes: this.getAttributes(),
        color: this.getColor(), // TYPES.NOTE and TYPES.CONVERSATION do not need a color but backend expects it
      };
      return serializeData;
    }
  }
});
