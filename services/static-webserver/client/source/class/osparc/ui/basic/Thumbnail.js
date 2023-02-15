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
  extend: qx.ui.core.Widget,

  /**
   * @param {String} source Source of the Image
   */
  construct: function(source) {
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

    if (source) {
      this.setSource(source);
    }

    const image = this.getChildControl("image");
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
    },

    minWidth: {
      check : "Integer",
      nullable : true,
      init : null,
      apply : "__applyMinWidth"
    },

    maxWidth: {
      check : "Integer",
      nullable : true,
      init : null,
      apply : "__applyMaxWidth"
    },

    minHeight: {
      check : "Integer",
      nullable : true,
      init : null,
      apply : "__applyMinHeight"
    },

    maxHeight: {
      check : "Integer",
      nullable : true,
      init : null,
      apply : "__applyMaxHeight"
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
            alignY: "middle"
          });
          this._add(control, {
            row: 1,
            column: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applySource: function(val) {
      const image = this.getChildControl("image");
      if (val) {
        image.setSource(val);
      }
    },

    __applyMinWidth: function(val) {
      const image = this.getChildControl("image");
      if (val) {
        image.setMinWidth(val);
      }
    },

    __applyMaxWidth: function(val) {
      const image = this.getChildControl("image");
      if (val) {
        image.setMaxWidth(val);
      }
    },

    __applyMinHeight: function(val) {
      const image = this.getChildControl("image");
      if (val) {
        image.setMinHeight(val);
      }
    },

    __applyMaxHeight: function(val) {
      const image = this.getChildControl("image");
      if (val) {
        image.setMaxHeight(val);
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
            image.setMaxWidth(this.getBounds().width);
          }
          if (this.getBounds() && this.getBounds().height < image.getMaxHeight()) {
            image.setMaxHeight(this.getBounds().height);
          }
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
