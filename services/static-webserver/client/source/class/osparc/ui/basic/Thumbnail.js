/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows an image well centered and scaled.
 *  ___________________________________
 * |     x     |flex Spacer|     x     |
 * |flex Spacer|   Image   |flex Spacer|
 * |_____x_____|flex Spacer|_____x_____|
 */
qx.Class.define("osparc.ui.basic.Thumbnail", {
  extend: osparc.ui.layout.CenteredGrid,

  /**
   * @param {String} source Source of the Image
   * @param {Number} maxWidth Maximum Width
   * @param {Number} maxHeight Maximum Height
   */
  construct: function(source, maxWidth, maxHeight) {
    this.base(arguments);

    if (source) {
      this.setSource(source);
    }
    const image = this.getChildControl("image");
    if (maxWidth) {
      image.setMaxWidth(maxWidth);
    }
    if (maxHeight) {
      image.setMaxHeight(maxHeight);
    }

    [
      "appear",
      "loaded"
    ].forEach(eventName => {
      image.addListener(eventName, () => this.recheckSize(), this);
    });
  },

  properties: {
    source: {
      check : "String",
      init : null,
      nullable : true,
      event : "changeSource",
      apply : "__applySource"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "image":
          control = new qx.ui.basic.Image().set({
            scale: true,
            allowStretchX: true,
            allowStretchY: true,
            alignX: "center",
            alignY: "middle",
          });
          this.addCenteredWidget(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __applySource: function(val) {
      const image = this.getChildControl("image");
      if (val) {
        if (!val.startsWith("osparc/") && osparc.utils.Utils.isValidHttpUrl(val)) {
          osparc.utils.Utils.setUrlSourceToImage(image, val);
        } else {
          image.setSource(val);
        }
      }
    },

    recheckSize: function() {
      const image = this.getChildControl("image");
      const source = image.getSource();
      if (source) {
        const srcWidth = qx.io.ImageLoader.getWidth(source);
        const srcHeight = qx.io.ImageLoader.getHeight(source);
        if (srcWidth && srcHeight) {
          const aspectRatio = srcWidth/srcHeight;
          if (this.getBounds() && this.getBounds().width < image.getMaxWidth()) {
            image.set({
              minWidth: parseInt(this.getBounds().width),
              maxWidth: parseInt(this.getBounds().width),
            });
          }
          if (this.getBounds() && this.getBounds().height < image.getMaxHeight()) {
            image.set({
              minHeight: parseInt(this.getBounds().height),
              maxHeight: parseInt(this.getBounds().height),
            });
          }
          const maxWidth = image.getMaxWidth();
          const maxHeight = image.getMaxHeight();

          if (maxWidth && maxHeight) {
            const newMaxHeight = maxWidth/aspectRatio;
            if (newMaxHeight < maxHeight) {
              image.set({
                minHeight: parseInt(newMaxHeight),
                maxHeight: parseInt(newMaxHeight),
              });
              return;
            }
            const newMaxWidth = maxHeight*aspectRatio;
            if (newMaxWidth < maxWidth) {
              image.set({
                minWidth: parseInt(newMaxWidth),
                maxWidth: parseInt(newMaxWidth),
              });
              return;
            }
            return;
          }

          if (maxWidth) {
            const newMaxHeight = maxWidth/aspectRatio;
            image.set({
              minHeight: parseInt(newMaxHeight),
              maxHeight: parseInt(newMaxHeight),
            });
            return;
          }

          if (maxHeight) {
            const newMaxWidth = maxHeight*aspectRatio;
            image.set({
              minWidth: parseInt(newMaxWidth),
              maxWidth: parseInt(newMaxWidth),
            });
            return;
          }
        }
      }
    }
  }
});
