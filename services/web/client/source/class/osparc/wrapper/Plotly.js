/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global Plotly */

/**
 * @asset(plotly/plotly.min.js)
 * @ignore(Plotly)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/plotly/plotly.js' target='_blank'>Plotly</a>
 */

qx.Class.define("osparc.wrapper.Plotly", {
  extend: qx.core.Object,

  statics: {
    NAME: "plotly",
    VERSION: "1.49.1",
    URL: "https://github.com/plotly/plotly.js"
  },

  construct: function() {
    this.base(arguments);

    this.__data = [];
    this.__layout = {};
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  events: {
    "plotlyLibReady": "qx.event.type.Data"
  },

  members: {
    __layout: null,
    __data: null,
    __plotId: null,

    init: function() {
      // initialize the script loading
      let plotlyPath = "plotly/plotly.min.js";
      let dynLoader = new qx.util.DynamicScriptLoader([
        plotlyPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(plotlyPath + " loaded");
        this.setLibReady(true);
        this.fireDataEvent("plotlyLibReady", true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.log("failed to load " + data.script);
        this.fireDataEvent("plotlyLibReady", false);
      }, this);

      dynLoader.start();
    },

    createEmptyPlot: function(id) {
      this.__plotId = id;
      const margin = 25;
      const bigFont = osparc.utils.Utils.getFont(14);
      const smallFont = osparc.utils.Utils.getFont(12);
      this.__layout = {
        titlefont: {
          color: "#bfbfbf",
          size: bigFont.getSize(),
          family: bigFont.getFamily()
        },
        font: {
          color: "#bfbfbf",
          size: smallFont.getSize(),
          family: smallFont.getFamily()
        },
        margin: {
          l: margin,
          r: margin,
          t: margin,
          b: margin,
          pad: 0
        },
        "plot_bgcolor": "rgba(0, 0, 0, 0)",
        "paper_bgcolor": "rgba(0, 0, 0, 0)"
      };
      this.__data = [];
      Plotly.newPlot(this.__plotId, this.__data, this.__layout);
    },

    resize: function() {
      let d3 = Plotly.d3;
      var gd3 = d3.select("div[id="+this.__plotId+"]");
      let gd = gd3.node();
      Plotly.Plots.resize(gd);
    },

    setData: function(ids, labels, values, tooltips, title) {
      this.__data = [{
        ids: ids,
        labels: labels,
        values: values,
        text: tooltips,
        textinfo: "label+percent",
        hoverinfo: "text",
        showlegend: false,
        type: "pie"
      }];
      this.__layout["title"] = title;

      Plotly.react(this.__plotId, this.__data, this.__layout);
    }
  }
});
