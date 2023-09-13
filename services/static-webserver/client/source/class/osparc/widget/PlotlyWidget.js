/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
  * Widget containing a Plotly dom element.
  * Data for being plotted can be dynamically set and rendered.
  */

qx.Class.define("osparc.widget.PlotlyWidget", {
  extend: qx.ui.core.Widget,

  /**
    * @param plotId {String} Element id to set it as dom attribute
    * @param data {Object} Plotly data
    * @param layout {Object} Plotly layout
    * @param config {Object} Plotly config
    */
  construct: function(plotId, data, layout, config = {}) {
    this.base(arguments);

    this.__plotId = plotId;
    this.addListenerOnce("appear", () => {
      if (osparc.wrapper.Plotly.getInstance().isLibReady()) {
        const plotlyPlaceholder = qx.dom.Element.create("div");
        qx.bom.element.Attribute.set(plotlyPlaceholder, "id", plotId);
        qx.bom.element.Style.set(plotlyPlaceholder, "width", "100%");
        qx.bom.element.Style.set(plotlyPlaceholder, "height", "100%");
        this.getContentElement().getDomElement().appendChild(plotlyPlaceholder);
        const {
          emptyData,
          emptyLayout
        } = osparc.wrapper.Plotly.createEmptyPlot(plotId, config);
        if (data) {
          osparc.wrapper.Plotly.setData(plotId, data);
          this.__data = data;
        } else {
          this.__data = emptyData;
        }
        if (layout) {
          osparc.wrapper.Plotly.setLayout(plotId, layout);
          this.__layout = layout;
        } else {
          this.__layout = emptyLayout;
        }
        if (layout) {
          osparc.wrapper.Plotly.setLayout(plotId, layout);
          this.__layout = layout;
        } else {
          this.__layout = emptyLayout;
        }
      } else {
        console.error("plotly.js was not loaded");
      }
    }, this);

    // this.addListener("resize", () => osparc.wrapper.Plotly.resize(this.__plotId), this);
  },

  members: {
    __plotId: null,
    __data: null,
    __layout: null,

    resize: function() {
      osparc.wrapper.Plotly.resize(this.__plotId);
    },

    setData: function(ids, labels, values, tooltips, title) {
      osparc.wrapper.Plotly.setData(this.__plotId, ids, labels, values, tooltips, title);
    }
  }
});
