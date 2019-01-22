/**
 * @asset(plotly/plotly.min.js)
 * @ignore(Plotly)
 */

/* global Plotly */

qx.Class.define("qxapp.wrappers.Plotly", {
  extend: qx.core.Object,

  statics: {
    NAME: "plotly",
    VERSION: "1.43.2",
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

      dynLoader.addListenerOnce("ready", function(e) {
        console.log(plotlyPath + " loaded");
        this.setLibReady(true);
        this.fireDataEvent("plotlyLibReady", true);
      }, this);

      dynLoader.addListener("failed", function(e) {
        let data = e.getData();
        console.log("failed to load " + data.script);
        this.fireDataEvent("plotlyLibReady", false);
      }, this);

      dynLoader.start();
    },

    createEmptyPlot: function(id) {
      this.__plotId = id;
      const margin = 60;
      this.__layout = {
        title: "My Title",
        margin: {
          l: margin,
          r: margin,
          t: margin,
          b: margin,
          pad: 25
        },
        height: 400,
        width: 500,
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

    setTitle: function(title) {
      this.__layout["title"] = title;
      Plotly.relayout(this.__plotId, this.__layout);
    },

    setData: function(xVals, yVals, xLabel, yLabel) {
      this.__data = [{
        values: [19, 26, 55],
        labels: ["Residential", "Non-Residential", "Utility"],
        type: "pie"
      }];

      Plotly.react(this.__plotId, this.__data, this.__layout);
    }
  }
});
