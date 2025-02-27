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
 * Widget that displays a SVG image and supports changing its color.
 * It is meant to be used for those images that are not available in the catalogs of font icons we include.
 */


qx.Class.define("osparc.ui.basic.SVGImage", {
  extend: osparc.ui.layout.CenteredGrid,

  /**
   * @param source
   */
  construct: function(source) {
    this.base(arguments);

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
      nullable: true,
      event: "changeImageColor",
      apply: "__applyImageColor"
    },
  },

  statics: {
    keywordToCSSFilter: function(keyword) {
      // use the following link to extended supported colors
      // https://isotropic.co/tool/hex-color-to-css-filter/
      let filter = null;
      switch (keyword) {
        case "danger-red": // "#FF2D2D"
          filter = "invert(13%) sepia(89%) saturate(5752%) hue-rotate(346deg) brightness(85%) contrast(109%)";
          break;
        case "warning-yellow": // #F8DB1F
          filter = "invert(90%) sepia(99%) saturate(7500%) hue-rotate(331deg) brightness(95%) contrast(108%)";
          break;
        case "ready-green": // #58A6FF
          filter = "invert(66%) sepia(24%) saturate(5763%) hue-rotate(188deg) brightness(101%) contrast(101%)";
          break;
        case "text": // light or dark
          if (qx.theme.manager.Meta.getInstance().getTheme().basename === "ThemeLight") {
            // ThemeLight #282828
            filter = "invert(10%) sepia(4%) saturate(19%) hue-rotate(354deg) brightness(102%) contrast(86%)";
          } else {
            // ThemeDark #D8D8D8
            filter = "invert(94%) sepia(0%) saturate(1442%) hue-rotate(148deg) brightness(97%) contrast(84%)";
          }
          break;
        case "strong-main": // it depends on the product
          if (qx.theme.manager.Meta.getInstance().getTheme().name.includes(".s4l.")) {
            // "rgba(0, 144, 208, 1)"
            filter = "invert(55%) sepia(73%) saturate(6976%) hue-rotate(177deg) brightness(100%) contrast(102%)";
          } else if (qx.theme.manager.Meta.getInstance().getTheme().name.includes(".tis.")) {
            // "rgba(105, 105, 255, 1)"
            filter = "invert(36%) sepia(74%) saturate(2007%) hue-rotate(225deg) brightness(102%) contrast(104%)";
          } else {
            // "rgba(131, 0, 191, 1)" osparc
            filter = "invert(13%) sepia(95%) saturate(6107%) hue-rotate(282deg) brightness(77%) contrast(115%)";
          }
      }
      return filter;
    },

    // not very accurate
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
    },

    setColorToImage: function(image, keywordOrRgb) {
      if (keywordOrRgb === null) {
        keywordOrRgb = "text";
      }
      let filterValue = this.self().keywordToCSSFilter(keywordOrRgb);
      if (filterValue === null) {
        const hexColor = qx.theme.manager.Color.getInstance().resolve(keywordOrRgb);
        const rgbColor = qx.util.ColorUtil.hexStringToRgb(hexColor);
        filterValue = this.self().rgbToCSSFilter(rgbColor);
      }
      const myStyle = {
        "filter": filterValue
      };
      image.getContentElement().setStyles(myStyle);
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
            allowGrowX: true,
            allowGrowY: true,
            alignX: "center",
            alignY: "middle"
          });
          this.addCenteredWidget(control);
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
      * @param keywordOrRgb {string} predefined keyword or rgb in the following format "0,255,0"
      */
    __applyImageColor: function(keywordOrRgb) {
      this.self().setColorToImage(this.getChildControl("image"), keywordOrRgb);
    },
  }
});
