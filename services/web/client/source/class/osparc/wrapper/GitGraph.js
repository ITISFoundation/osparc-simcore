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
      const textColor = qx.theme.manager.Color.getInstance().resolve("text");
      return {
        colors: [
          "#1486da",
          "#e01a94",
          "#e01a94",
          "#e01a94",
          "#e01a94"
        ],
        commit: {
          spacing: 20,
          dot: {
            size: 3
          },
          message: {
            displayAuthor: false,
            displayBranch: false,
            displayHash: false,
            color: textColor,
            font: "normal 13px Roboto"
          },
          shouldDisplayTooltipsInCompactMode: true,
          tooltipHTMLFormatter: commit => commit.message
        },
        branch: {
          spacing: 20,
          lineWidth: 1,
          label: {
            display: false,
            bgColor: "transparent",
            strokeColor: "transparent"
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
      const myTemplate = GitgraphJS.templateExtend("metro", this.self().getTemplateConfig());

      const gitgraph = GitgraphJS.createGitgraph(graphContainer, {
        // "mode": "compact",
        "template": myTemplate
      });
      // gitgraph.canvas.addEventListener("commit:mouseover", e => this.__mouseOver(e));
      // gitgraph.canvas.addEventListener("commit:mouseout", e => this.__mouseOut(e));
      return gitgraph;
    },

    __mouseOver: function(e) {
      console.log("You're over a commit", e.data);
      this.style.cursor = "pointer";
    },

    __mouseOut: function(e) {
      console.log("You just left this commit", e.data);
      this.style.cursor = "auto";
    },

    example: function(gitgraph) {
      const master = gitgraph.branch("master");
      master.commit("Initial commit");
      master.commit("Some changes");

      const it1 = master.branch("iteration-1");
      it1.commit("[iteration-1] - x=1");

      const it2 = master.branch("iteration-2");
      it2.commit("x=2");

      const it3 = master.branch("iteration-3");
      it3.commit("x=3");

      master.commit("Changes after iterations");
    }
  }
});
