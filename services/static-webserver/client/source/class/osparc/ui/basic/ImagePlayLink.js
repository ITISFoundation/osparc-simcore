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

    this.addListener("pointerover", this.__showPlayLink);
  },

  properties: {
    link: {
      check: "String",
      init: null,
      nullable: false
    }
  },

  members: {
    __hoverImage: null,

    __createHoverImage: function() {
      const element = this.getContentElement().getDomElement();
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(element);

      const image = new qx.ui.basic.Image().set({
        source: "@FontAwesome5Solid/play/96",
        textColor: "strong-main",
        height,
        width,
        alignX: "center",
        alignY: "middle",
        cursor: "pointer"
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
      if (this.__hoverImage === null) {
        const hoverCanvas = this.__hoverImage = this.__createHoverImage();
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
      }
    },

    __hidePlayLink: function() {
      if (this.__hoverImage) {
        const root = qx.core.Init.getApplication().getRoot();
        root.remove(this.__hoverImage);
        this.__hoverImage.exclude();
        this.__hoverImage = null;
      }
    }
  }
});
