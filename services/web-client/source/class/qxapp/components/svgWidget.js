/* global qxapp */

const LINKS_LAYER_ID = "drawing";

qx.Class.define("qxapp.components.SvgWidget", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    let scope = this;
    this.addListenerOnce("appear", function() {
      scope._svgWrapper = new qxapp.wrappers.SvgWrapper();
      scope._svgWrapper.addListener(("SvgLibReady"), function(e) {
        let ready = e.getData();
        if (ready) {
          let svgPlaceholder = qx.dom.Element.create("div");
          qx.bom.element.Attribute.set(svgPlaceholder, "id", LINKS_LAYER_ID);
          qx.bom.element.Style.set(svgPlaceholder, "z-index", 12);
          qx.bom.element.Style.set(svgPlaceholder, "width", "100%");
          qx.bom.element.Style.set(svgPlaceholder, "height", "100%");
          scope.getContentElement().getDomElement()
            .appendChild(svgPlaceholder);

          scope._linksCanvas = scope._svgWrapper.createEmptyCanvas(LINKS_LAYER_ID);
        } else {
          console.log("svg.js was not loaded");
        }
      }, scope);

      scope._svgWrapper.init();
    }, scope);
  },

  members: {
    _svgWrapper: null,
    _linksCanvas: null,

    _getControls(x1, y1, x2, y2) {
      const offset = 100;
      return [{
        x: x1,
        y: y1
      }, {
        x: x1+offset,
        y: y1
      }, {
        x: x2-offset,
        y: y2
      }, {
        x: x2,
        y: y2
      }];
    },

    drawCurve: function(x1, y1, x2, y2) {
      const controls = this._getControls(x1, y1, x2, y2);
      return this._svgWrapper.drawCurve(this._linksCanvas, controls);
    },

    updateCurve: function(curve, x1, y1, x2, y2) {
      const controls = this._getControls(x1, y1, x2, y2);
      this._svgWrapper.updateCurve(curve, controls);
    }
  }
});
