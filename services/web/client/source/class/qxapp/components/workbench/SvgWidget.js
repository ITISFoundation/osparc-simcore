const LINKS_LAYER_ID = "drawing";

qx.Class.define("qxapp.components.workbench.SvgWidget", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base();

    this.addListenerOnce("appear", function() {
      this.__SvgWrapper = new qxapp.wrappers.SvgWrapper();
      this.__SvgWrapper.addListener(("SvgLibReady"), function(e) {
        let ready = e.getData();
        if (ready) {
          let svgPlaceholder = qx.dom.Element.create("div");
          qx.bom.element.Attribute.set(svgPlaceholder, "id", LINKS_LAYER_ID);
          qx.bom.element.Style.set(svgPlaceholder, "z-index", 12);
          qx.bom.element.Style.set(svgPlaceholder, "width", "100%");
          qx.bom.element.Style.set(svgPlaceholder, "height", "100%");
          this.getContentElement().getDomElement()
            .appendChild(svgPlaceholder);

          this.__LinksCanvas = this.__SvgWrapper.createEmptyCanvas(LINKS_LAYER_ID);
        } else {
          console.log("svg.js was not loaded");
        }
      }, this);

      this.__SvgWrapper.init();
    }, this);
  },

  members: {
    __SvgWrapper: null,
    __LinksCanvas: null,

    __getControls(x1, y1, x2, y2) {
      const offset = 50;
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
      const controls = this.__getControls(x1, y1, x2, y2);
      return this.__SvgWrapper.drawCurve(this.__LinksCanvas, controls);
    },

    updateCurve: function(curve, x1, y1, x2, y2) {
      const controls = this.__getControls(x1, y1, x2, y2);
      this.__SvgWrapper.updateCurve(curve, controls);
    }
  }
});
