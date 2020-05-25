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
 *  _______________________
 * |   x   |Spacer |   x   |
 * |Spacer | Image |Spacer |
 * |___x___|Spacer_|___x___|
 */
qx.Class.define("osparc.component.widget.Thumbnail", {
  extend: qx.ui.core.Widget,

  construct: function(source, maxWidth) {
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
      allowStretchY: true,
      maxWidth: maxWidth || 200
    });

    if (source) {
      image.setSource(source);
    }

    image.addListener("changeSource", e => {
      this.__calculateMaxHeight();
    }, this);
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
        const aspectRatio = width/height;
        const maxHeight = image.getMaxWidth()/aspectRatio;
        console.log(width, height);
        console.log(image.getMaxWidth(), maxHeight);
        image.setMaxHeight(parseInt(maxHeight));
      }
    }
  }
});
