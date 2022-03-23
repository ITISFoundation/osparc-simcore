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

/* global Plotly */

/**
 * @asset(plotly/plotly-2.9.0.min.js)
 * @ignore(Plotly)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/plotly/plotly.js' target='_blank'>Plotly</a>
 */

qx.Class.define("osparc.wrapper.Plotly", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  statics: {
    NAME: "Plotly",
    VERSION: "2.9.0",
    URL: "https://github.com/plotly/plotly.js",

    createEmptyPlot: function(plotId) {
      return osparc.wrapper.Plotly.getInstance().createEmptyPlot(plotId);
    },

    setLayout: function(plotId, data) {
      return osparc.wrapper.Plotly.getInstance().setLayout(plotId, data);
    },

    setData: function(plotId, data) {
      return osparc.wrapper.Plotly.getInstance().setData(plotId, data);
    },

    resize: function(plotId) {
      return osparc.wrapper.Plotly.getInstance().resize(plotId);
    },

    getDefaultLayout: function() {
      const textColor = qx.theme.manager.Color.getInstance().resolve("text");
      const bigFont = qx.theme.manager.Font.getInstance().resolve("text-12");
      const smallFont = qx.theme.manager.Font.getInstance().resolve("text-9");
      const margin = 25;
      return {
        autoscale: true,
        titlefont: {
          color: textColor,
          size: bigFont.getSize(),
          family: bigFont.getFamily()
        },
        font: {
          color: textColor,
          size: smallFont.getSize(),
          family: smallFont.getFamily()
        },
        margin: {
          l: margin,
          r: margin,
          t: margin,
          b: margin,
          pad: 10
        },
        "paper_bgcolor": "rgba(0, 0, 0, 0)"
      };
    },

    getDefaultGaugeData: function() {
      return [{
        domain: {
          x: [0, 1],
          y: [0, 1]
        },
        value: 0,
        title: {
          text: "title"
        },
        type: "indicator",
        mode: "gauge+number",
        gauge: {
          axis: {
            range: [null, 100]
          }
        }
      }];
    }
  },

  members: {
    init: function() {
      return new Promise((resolve, reject) => {
        if (this.getLibReady()) {
          resolve();
          return;
        }

        // initialize the script loading
        const plotlyPath = "plotly/plotly-2.9.0.min.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          plotlyPath
        ]);

        dynLoader.addListenerOnce("ready", () => {
          console.log(plotlyPath + " loaded");
          this.setLibReady(true);
          resolve();
        }, this);

        dynLoader.addListener("failed", e => {
          const data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    createEmptyPlot: function(plotId) {
      const emptyData = [];
      const emptyLayout = this.self().getDefaultLayout();
      Plotly.newPlot(plotId, emptyData, emptyLayout);
      return {
        emptyData,
        emptyLayout
      };
    },

    setData: function(plotId, data) {
      Plotly.react(plotId, data);
    },

    setLayout: function(plotId, layout) {
      Plotly.relayout(plotId, layout);
    },

    resize: function(plotId) {
      const d3 = Plotly.d3;
      const gd3 = d3.select("div[id="+plotId+"]");
      const gd = gd3.node();
      Plotly.Plots.resize(gd);
    }
  }
});
