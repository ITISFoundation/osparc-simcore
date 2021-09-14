/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global GitgraphJS */

/**
 * @asset(gitgraph/gitgraph.js)
 * @ignore(GitgraphJS)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/nicoespeon/gitgraph.js/tree/master/packages/gitgraph-js' target='_blank'>GitGraph</a>
 */

qx.Class.define("osparc.wrapper.GitGraph", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "GitGraph",
    VERSION: "1.4.0",
    URL: "https://github.com/nicoespeon/gitgraph.js/tree/master/packages/gitgraph-js",

    getTemplateConfig: function() {
      return {
        colors: [
          "#F00",
          "#0F0",
          "#0F0",
          "#0F0",
          "#0F0",
          "#0F0"
        ], // branches colors, 1 per column
        commit: {
          spacingX: 5,
          spacingY: 10,
          dot: {
            size: 6
          },
          message: {
            displayAuthor: false,
            displayBranch: false,
            displayHash: false,
            font: "normal 11pt Roboto"
          },
          shouldDisplayTooltipsInCompactMode: true, // default = true
          tooltipHTMLFormatter: commit => {
            console.log(commit);
            return commit.sha1 + ": " + commit.message;
          }
        },
        branch: {
          lineWidth: 3,
          spacingX: 10,
          spacingY: 15,
          showLabel: true // display branch names on graph
        }
      };
    }
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
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
        const gitGraphPath = "gitgraph/gitgraph.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          gitGraphPath
        ]);

        dynLoader.addListenerOnce("ready", e => {
          console.log(gitGraphPath + " loaded");
          this.setLibReady(true);
          resolve();
        }, this);

        dynLoader.addListener("failed", e => {
          let data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    createGraph: function(graphContainer) {
      // osparc.utils.Utils.setZoom(graphContainer, 0.6);

      const myTemplate = GitgraphJS.templateExtend("metro", this.self().getTemplateConfig());

      // Instantiate the graph.
      const gitgraph = GitgraphJS.createGitgraph(graphContainer, {
        template: myTemplate
      });
      return gitgraph;
    },

    example: function(gitgraph) {
      const master = gitgraph.branch("master");
      master.commit("Initial commit");
      master.commit("Some changes");

      const it1 = master.branch("iteration-1");
      it1.commit("x=1");

      const it2 = master.branch("iteration-2");
      it2.commit("x=2");

      const it3 = master.branch("iteration-3");
      it3.commit("x=3");
    }
  }
});
