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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this.__commits = [];
  },

  statics: {
    NAME: "GitGraph",
    VERSION: "1.4.0",
    URL: "https://github.com/nicoespeon/gitgraph.js/tree/master/packages/gitgraph-js",

    COMMIT_SPACING: 20,

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
          spacing: osparc.wrapper.GitGraph.COMMIT_SPACING,
          dot: {
            size: 3
          },
          message: {
            displayAuthor: false,
            displayBranch: false,
            displayHash: false,
            color: textColor,
            font: "normal 13px Roboto"
          }
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

  events: {
    "snapshotTap": "qx.event.type.Data"
  },

  members: {
    __gitGraphCanvas: null,
    __gitgraph: null,

    init: function(gitGraphCanvas, gitGraphInteract) {
      return new Promise((resolve, reject) => {
        this.__gitGraphCanvas = gitGraphCanvas;
        this.__gitGraphInteract = gitGraphInteract;
        const el = gitGraphCanvas.getContentElement().getDomElement();
        if (this.getLibReady()) {
          const gitgraph = this.__createGraph(el);
          resolve(gitgraph);
          return;
        }

        // initialize the script loading
        const gitGraphPath = "gitgraph/gitgraph.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          gitGraphPath
        ]);

        dynLoader.addListenerOnce("ready", e => {
          console.log(gitGraphPath + " loaded");
          const gitgraph = this.__createGraph(el);
          this.setLibReady(true);
          resolve(gitgraph);
        }, this);

        dynLoader.addListener("failed", e => {
          let data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    __createGraph: function(graphContainer) {
      const myTemplate = GitgraphJS.templateExtend("metro", this.self().getTemplateConfig());

      const gitgraph = this.__gitgraph = GitgraphJS.createGitgraph(graphContainer, {
        // "mode": "compact",
        "template": myTemplate
      });
      return gitgraph;
    },

    commit: function(branch, commitData) {
      branch.commit(commitData["tags"]);

      const widget = new qx.ui.core.Widget().set({
        opacity: 0.1,
        height: this.self().COMMIT_SPACING,
        minWidth: 50,
        allowGrowX: true
      });
      const texts = [];
      if ("message" in commitData && commitData["message"]) {
        texts.push(commitData["message"]);
      }
      if ("createdAt" in commitData && commitData["createdAt"]) {
        texts.push(commitData["createdAt"]);
      }
      const hintText = texts.join("<br>");
      const hint = new osparc.ui.hint.Hint(widget, hintText);
      this.__gitGraphInteract.add(widget, {
        top: this.self().COMMIT_SPACING*this.__commits.length + 3,
        left: 0,
        right: 0
      });
      this.__commits.push({
        id: commitData["id"],
        branch,
        msg: commitData["tags"],
        widget
      });
      const bgColor = widget.getBackgroundColor();
      widget.addListener("mouseover", () => {
        widget.set({
          backgroundColor: "white",
          cursor: "pointer"
        });
        hint.show();
      });
      widget.addListener("mouseout", () => {
        widget.set({
          backgroundColor: bgColor,
          cursor: "auto"
        });
        hint.exclude();
      });
      widget.addListener("tap", () => this.fireDataEvent("snapshotTap", commitData["id"]));
    },

    buildExample: function() {
      const master = this.__gitgraph.branch("master");
      this.commit(master, "Initial commit");
      this.commit(master, "Some changes");

      const it1 = master.branch("iteration-1");
      this.commit(it1, "x=1");

      const it2 = master.branch("iteration-2");
      this.commit(it2, "x=2");

      const it3 = master.branch("iteration-3");
      this.commit(it3, "x=3");

      this.commit(master, "Changes after iterations");
    },

    populateGraph: function(snapshots) {
      const master = this.__gitgraph.branch("master");
      snapshots.forEach(snapshot => {
        const date = new Date(snapshot["created_at"]);
        const commitData = {
          id: snapshot["id"],
          tags: snapshot["tags"].join(", "),
          message: snapshot["message"],
          createdAt: osparc.utils.Utils.formatDateAndTime(date),
          parentUuid: snapshot["parent_uuid"]
        };
        this.commit(master, commitData);
      });
    }
  }
});
