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
qx.Class.define("osparc.component.widget.Thumbnail", {
  extend: qx.ui.core.Widget,

  /**
   * @param {String} source Source of the Image
   * @param {Number} maxWidth Maximum Width
   * @param {Number} maxHeight Maximum Height
   */
  construct: function(source, maxWidth, maxHeight) {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid();
    layout.setRowFlex(0, 1);
    layout.setRowFlex(2, 1);
    layout.setColumnFlex(0, 1);
    layout.setColumnFlex(2, 1);
    this._setLayout(layout);

    [
      [0, 0],
      [0, 1],
      [0, 2],
      [1, 0],
      [1, 2],
      [2, 0],
      [2, 1],
      [2, 2]
    ].forEach(quad => {
      const empty = new qx.ui.core.Spacer();
      this._add(empty, {
        row: quad[0],
        column: quad[1]
      });
    });

    const image = this.getChildControl("image").set({
      scale: true,
      allowStretchX: true,
      allowStretchY: true
    });

    if (source) {
      image.setSource(source);
    }

    if (maxWidth) {
      image.setMaxWidth(maxWidth);
    }

    if (maxHeight) {
      image.setMaxHeight(maxHeight);
    }

    [
      "changeSource",
      "loaded"
    ].forEach(eventName => {
      image.addListener(eventName, e => {
        this.__calculateMaxHeight();
      }, this);
    });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "image":
          control = new qx.ui.basic.Image();
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __calculateMaxHeight: function() {
      const image = this.getChildControl("image");
      const source = image.getSource();
      if (source) {
        const width = qx.io.ImageLoader.getWidth(source);
        const height = qx.io.ImageLoader.getHeight(source);
        if (width && height) {
          const aspectRatio = width/height;
          const maxWidth = image.getMaxWidth();
          const maxHeight = image.getMaxHeight();

          if (maxWidth && maxHeight) {
            const newMaxHeight = maxWidth/aspectRatio;
            if (newMaxHeight < maxHeight) {
              image.setMaxHeight(parseInt(newMaxHeight));
              return;
            }
            const newMaxWidth = maxHeight*aspectRatio;
            if (newMaxWidth < maxWidth) {
              image.setMaxWidth(parseInt(newMaxWidth));
              return;
            }
            return;
          }

          if (maxWidth) {
            const newMaxHeight = maxWidth/aspectRatio;
            image.setMaxHeight(parseInt(newMaxHeight));
            return;
          }

          if (maxHeight) {
            const newMaxWidth = maxHeight*aspectRatio;
            image.setMaxWidth(parseInt(newMaxWidth));
            return;
          }
        }
      }
    }
  }
});
