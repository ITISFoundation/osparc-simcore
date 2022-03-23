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
 * @asset(plotly/plotly-basic-2.11.1.min.js)
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
    VERSION: "2.11.1",
    URL: "https://github.com/plotly/plotly.js",

    createEmptyPlot: function(plotId) {
      return osparc.wrapper.Plotly.getInstance().createEmptyPlot(plotId);
    },

    setData: function(plotId, ids, labels, values, tooltips, title) {
      return osparc.wrapper.Plotly.getInstance().setData(plotId, ids, labels, values, tooltips, title);
    },

    resize: function(plotId) {
      return osparc.wrapper.Plotly.getInstance().resize(plotId);
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
        const plotlyPath = "plotly/plotly-basic-2.11.1.min.js";
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
      const margin = 25;
      const bigFont = qx.theme.manager.Font.getInstance().resolve("text-14");
      const smallFont = qx.theme.manager.Font.getInstance().resolve("text-12");
      const layout = {
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
      const data = [];
      console.log("newPlot", plotId, data, layout);
      Plotly.newPlot(plotId, data, layout);
      return {
        data,
        layout
      };
    },

    setData: function(plotId, ids, labels, values, tooltips, title) {
      const data = [{
        ids: ids,
        labels: labels,
        values: values,
        text: tooltips,
        textinfo: "label+percent",
        hoverinfo: "text",
        showlegend: false,
        type: "pie"
      }];
      const layout = {
        title
      };

      Plotly.react(plotId, data, layout);
    },

    resize: function(plotId) {
      const d3 = Plotly.d3;
      const gd3 = d3.select("div[id="+plotId+"]");
      const gd = gd3.node();
      Plotly.Plots.resize(gd);
    }
  }
});
