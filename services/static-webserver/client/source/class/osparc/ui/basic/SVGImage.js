/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that displays an svg image and support changing its color.
 * It is meant to be used for those images that are not available in the catalog of font icons we include.
 */


qx.Class.define("osparc.ui.basic.SVGImage", {
  extend: qx.ui.core.Widget,

  /**
   * @param source
   */
  construct: function(source) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      alignX: "center",
      alignY: "middle"
    });

    if (source) {
      this.setSource(source);
    }
  },

  properties: {
    source: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__applySource"
    },

    imageColor: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeImageColor",
      apply: "__applyImageColor"
    },
  },

  statics: {
    rgbToCSSFilter: function(rgb) {
      const [r, g, b] = rgb.split(",").map(Number);

      let [rf, gf, bf] = [r / 255, g / 255, b / 255];
      let [mi, ma] = [Math.min(rf, gf, bf), Math.max(rf, gf, bf)];
      let [h, s, l] = [0, 0, (mi + ma) / 2];

      if (mi !== ma) {
        s = l < 0.5 ? (ma - mi) / (ma + mi) : (ma - mi) / (2 - ma - mi);
        switch (ma) {
          case rf:
            h = (gf - bf) / (ma - mi);
            break;
          case gf:
            h = 2 + (bf - rf) / (ma - mi);
            break;
          case bf:
            h = 4 + (rf - gf) / (ma - mi);
            break;
        }
      }

      h = Math.round(h * 60);
      if (h < 0) {
        h += 360;
      }
      s = Math.round(s * 100);
      l = Math.round(l * 100);

      const invertValue = l2 => 100 - l2;
      const sepiaValue = s2 => s2;
      const saturateValue = s3 => s3;
      const brightnessValue = l3 => l3;
      const contrastValue = l4 => l4 > 50 ? 50 : l4;
      return `invert(${invertValue(l)}%) sepia(${sepiaValue(s)}%) saturate(${saturateValue(s)}%) hue-rotate(${h}deg) brightness(${brightnessValue(l)}%) contrast(${contrastValue(l)}%)`;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "image":
          control = new qx.ui.basic.Image().set({
            scale: true,
            alignX: "center",
            alignY: "middle"
          });
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applySource: function(src) {
      if (src && src.includes(".svg")) {
        this.getChildControl("image").setSource(src);
      }
    },

    /**
      * @param rgb string in the following format: "255,0,0"
      */
    __applyImageColor: function(rgb) {
      const filterValue = this.self().rgbToCSSFilter(rgb);
      const myStyle = {
        "filter": filterValue
      };
      this.getChildControl("image").getContentElement().setStyles(myStyle);
    },

    setSize: function(size) {
      this.getChildControl("image").set({
        height: size.height,
        width: size.width
      });
    }
  }
});
