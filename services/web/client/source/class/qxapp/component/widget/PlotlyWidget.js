qx.Class.define("qxapp.component.widget.PlotlyWidget", {
  extend: qx.ui.core.Widget,

  construct: function(elemId) {
    this.base();

    this.addListenerOnce("appear", () => {
      this.__plotlyWrapper = new qxapp.wrappers.Plotly();
      this.__plotlyWrapper.addListener(("plotlyLibReady"), e => {
        let ready = e.getData();
        if (ready) {
          let plotlyPlaceholder = qx.dom.Element.create("div");
          qx.bom.element.Attribute.set(plotlyPlaceholder, "id", elemId);
          qx.bom.element.Style.set(plotlyPlaceholder, "width", "100%");
          qx.bom.element.Style.set(plotlyPlaceholder, "height", "100%");
          this.getContentElement().getDomElement()
            .appendChild(plotlyPlaceholder);
          this.__plotlyWrapper.createEmptyPlot(elemId);
          this.__plotlyWrapper.setData();
        } else {
          console.debug("plotly.js was not loaded");
        }
      }, this);

      this.__plotlyWrapper.init();
    }, this);

    this.addListener("resize", function() {
      if (this.__plotlyWrapper) {
        this.__plotlyWrapper.resize();
      }
    }, this);
  },

  members: {
    __plotlyWrapper: null,

    resize: function() {
      this.__plotlyWrapper.resize();
    },

    setData: function(xVals, yVals, xLabel = "no label", yLabel = "no label") {
      this.__plotlyWrapper.setData(xVals, yVals, xLabel, yLabel);
    },

    setDataY2: function(xVals, y2Vals, xLabel = "no label", y2Label = "no label") {
      this.__plotlyWrapper.setDataY2(xVals, y2Vals, xLabel, y2Label);
    }
  }
});
