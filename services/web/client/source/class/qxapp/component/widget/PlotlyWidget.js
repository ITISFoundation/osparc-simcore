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
          this.fireDataEvent("plotlyWidgetReady", true);
        } else {
          console.debug("plotly.js was not loaded");
          this.fireDataEvent("plotlyWidgetReady", false);
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

  events: {
    "plotlyWidgetReady": "qx.event.type.Data"
  },

  members: {
    __plotlyWrapper: null,

    resize: function() {
      this.__plotlyWrapper.resize();
    },

    setData: function(ids, labels, values) {
      this.__plotlyWrapper.setData(ids, labels, values);
    }
  }
});
