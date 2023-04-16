/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.basic.ImagePlayLink", {
  extend: qx.ui.basic.Image,

  construct: function(source, link) {
    this.base(arguments, source);

    this.set({
      cursor: "pointer"
    });
    this.getContentElement().setStyles({
      "border-radius": "8px"
    });

    if (link) {
      this.setLink(link);
    }

    this.addListener("pointerover", this.__showPlayLink, this);
  },

  properties: {
    link: {
      check: "String",
      init: null,
      nullable: false
    }
  },

  members: {
    __hoverCanvas: null,
    __hoverPlay: null,

    __createHoverImage: function() {
      const element = this.getContentElement().getDomElement();
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(element);

      const image = new qx.ui.basic.Image().set({
        height,
        width,
        cursor: "pointer"
      });
      image.addListener("pointerout", this.__hidePlayLink, this);
      image.addListener("tap", this.__openPlayLink, this);
      return image;
    },

    __createHoverCanvas: function() {
      const image = this.__createHoverImage().set({
        backgroundColor: "text",
        opacity: 0.5
      });
      image.getContentElement().setStyles({
        "border-radius": "8px"
      });
      return image;
    },

    __createHoverPlay: function() {
      const element = this.getContentElement().getDomElement();
      const {
        height
      } = qx.bom.element.Dimension.getSize(element);

      const playSize = 96;
      const image = this.__createHoverImage().set({
        source: "@FontAwesome5Solid/play/" + playSize,
        textColor: "strong-main",
        alignX: "center",
        alignY: "middle",
        cursor: "pointer",
        paddingTop: parseInt(height/2 - playSize/2)
      });
      return image;
    },

    __openPlayLink: function() {
      if (this.getLink()) {
        window.open(this.getLink(), "_blank");
      }
    },

    __showPlayLink: function() {
      if (this.__hoverCanvas === null) {
        const hoverCanvas = this.__hoverCanvas = this.__createHoverCanvas();
        const hoverPlay = this.__hoverPlay = this.__createHoverPlay();
        const element = this.getContentElement().getDomElement();
        const {
          top,
          left
        } = qx.bom.element.Location.get(element);
        const root = qx.core.Init.getApplication().getRoot();
        root.add(hoverCanvas, {
          top,
          left
        });
        root.add(hoverPlay, {
          top,
          left
        });
      }
    },

    __hidePlayLink: function() {
      if (this.__hoverCanvas) {
        const root = qx.core.Init.getApplication().getRoot();
        root.remove(this.__hoverCanvas);
        this.__hoverCanvas.exclude();
        this.__hoverCanvas = null;
      }
      if (this.__hoverPlay) {
        const root = qx.core.Init.getApplication().getRoot();
        root.remove(this.__hoverPlay);
        this.__hoverPlay.exclude();
        this.__hoverPlay = null;
      }
    }
  }
});
