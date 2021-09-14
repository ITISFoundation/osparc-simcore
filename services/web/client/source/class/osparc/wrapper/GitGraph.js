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
          "#00F"
        ], // branches colors, 1 per column
        branch: {
          lineWidth: 4,
          spacingX: 25,
          showLabel: true // display branch names on graph
        },
        commit: {
          spacingY: -40,
          dot: {
            size: 6
          },
          message: {
            displayAuthor: true,
            displayBranch: false,
            displayHash: false,
            font: "normal 10pt Roboto"
          },
          shouldDisplayTooltipsInCompactMode: true, // default = true
          tooltipHTMLFormatter: commit => {
            console.log(commit);
            return commit.sha1 + ": " + commit.message;
          }
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
      // Simulate git commands with Gitgraph API.
      const master = gitgraph.branch("master");
      master.commit("Initial commit");

      const develop = master.branch("develop");
      develop.commit("Add TypeScript");

      const aFeature = develop.branch("a-feature");
      aFeature
        .commit("Make it work")
        .commit("Make it fast");

      develop.merge(aFeature);
      develop.commit("Prepare v1");

      master.merge(develop).tag("v1.0.0");
    }
  }
});
