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

    __createHoverCanvas: function() {
      const element = this.getContentElement().getDomElement();
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(element);

      const image = new qx.ui.basic.Image().set({
        backgroundColor: "text",
        opacity: 0.5,
        height,
        width,
        cursor: "pointer"
      });
      image.addListener("pointerout", this.__hidePlayLink, this);
      image.addListener("tap", this.__openPlayLink, this);
      return image;
    },

    __createHoverPlay: function() {
      const element = this.getContentElement().getDomElement();
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(element);

      const playSize = 96;
      const image = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/play/" + playSize,
        textColor: "strong-main",
        height,
        width,
        alignX: "center",
        alignY: "middle",
        cursor: "pointer",
        paddingTop: parseInt(height/2 - playSize/2)
      });
      image.addListener("pointerout", this.__hidePlayLink, this);
      image.addListener("tap", this.__openPlayLink, this);
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
