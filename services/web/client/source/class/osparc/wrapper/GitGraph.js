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

    __dotClick: function(commit) {
      console.log("Click on dot", commit);
    },

    __dotOver: function(commit) {
      console.log("You're over a commit", commit);
      this.set({
        cursor: "pointer"
      });
    },

    __dotOut: function(commit) {
      console.log("You just left this commit", commit);
      this.set({
        cursor: "auto"
      });
    },

    __messageClick: function(commit) {
      console.log("Click on message", commit);
    },

    commit: function(branch, msg, id) {
      const that = this;
      branch.commit({
        subject: msg,
        onClick(commit) {
          // eslint-disable-next-line no-underscore-dangle
          that.__dotClick(commit);
        },
        onMouseOver(commit) {
          // eslint-disable-next-line no-underscore-dangle
          that.__dotOver(commit);
        },
        onMouseOut(commit) {
          // eslint-disable-next-line no-underscore-dangle
          that.__dotOut(commit);
        },
        onMessageClick(commit) {
          // eslint-disable-next-line no-underscore-dangle
          that.__messageClick(commit);
        }
      });

      const widget = new qx.ui.core.Widget().set({
        opacity: 0.1,
        height: 20,
        minWidth: 50,
        allowGrowX: true
      });
      this.__gitGraphInteract.add(widget, {
        top: 20*this.__commits.length + 3,
        left: 0,
        right: 0
      });
      this.__commits.push({
        id,
        branch,
        msg,
        widget
      });
      const bgColor = widget.getBackgroundColor();
      widget.addListener("mouseover", () => {
        widget.set({
          backgroundColor: "white",
          cursor: "pointer"
        });
      });
      widget.addListener("mouseout", () => {
        widget.set({
          backgroundColor: bgColor,
          cursor: "auto"
        });
      });
      widget.addListener("tap", () => {
        this.fireDataEvent("snapshotTap", id);
      });
    },

    addCommit: function(branch, commitData) {
      this.commit(branch, commitData["createdAt"] + " - " + commitData["tags"], commitData["id"]);
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
        this.addCommit(master, commitData);
      });
    }
  }
});
