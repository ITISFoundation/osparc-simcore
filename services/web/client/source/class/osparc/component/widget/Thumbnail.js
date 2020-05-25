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
   * @param {Number} maxWidth Maximum constraint Width
   * @param {Number} maxHeight Maximum constraint Height
   */
  construct: function(source, maxWidth, maxHeight) {
    this.base(arguments);

    const layout = new qx.ui.layout.Grid(0, 0);
    layout.setRowFlex(0, 1);
    layout.setRowFlex(2, 1);
    layout.setColumnFlex(0, 1);
    layout.setColumnFlex(2, 1);

    this._setLayout(layout);

    this._add(new qx.ui.core.Spacer(), {
      row: 0,
      column: 1
    });

    this._add(new qx.ui.core.Spacer(), {
      row: 1,
      column: 0
    });

    this._add(new qx.ui.core.Spacer(), {
      row: 1,
      column: 2
    });

    this._add(new qx.ui.core.Spacer(), {
      row: 2,
      column: 1
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
          const maxHeight = image.getMaxWidth()/aspectRatio;
          console.log(width, height);
          console.log(image.getMaxWidth(), maxHeight);
          image.setMaxHeight(parseInt(maxHeight));
        }
      }
    }
  }
});
