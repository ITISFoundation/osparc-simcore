/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget containing a Plotly dom element.
 *
 * Data for being plotted can be dynamically set adn rendered.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let plotlyWidget = new osparc.component.widget.PlotlyWidget("elemId");
 *   this.getRoot().add(plotlyWidget);
 * </pre>
 */

qx.Class.define("osparc.component.widget.PlotlyWidget", {
  extend: qx.ui.core.Widget,

  /**
    * @param elemId {String} Element id to set it as dom attribute
  */
  construct: function(elemId) {
    this.base();

    this.addListenerOnce("appear", () => {
      this.__plotlyWrapper = new osparc.wrapper.Plotly();
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

    setData: function(ids, labels, values, tooltips, title) {
      this.__plotlyWrapper.setData(ids, labels, values, tooltips, title);
    }
  }
});
