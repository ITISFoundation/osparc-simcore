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
      const masterColor = "#1486da";
      const iterationColor = "#e01a94";
      const colors = Array(50).fill(iterationColor);
      colors.unshift(masterColor);
      return {
        colors: colors,
        commit: {
          spacing: osparc.wrapper.GitGraph.COMMIT_SPACING,
          dot: {
            size: 3
          },
          message: {
            display: false,
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
    __selectedCommit: null,
    __commits: null,
    __branches: null,
    __parentIDs: null,

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

    __commit: function(branch, commitData, isCurrent = false) {
      if (isCurrent) {
        branch.commit({
          subject: commitData["tags"],
          style: {
            message: {
              font: "bold 13px Roboto"
            }
          }
        });
      } else {
        branch.commit(commitData["tags"]);
      }
      branch["lastCommit"] = commitData["id"];

      // Widget for highlighting the overed commit with hint
      const widget = new qx.ui.core.Widget().set({
        opacity: 0.1,
        height: this.self().COMMIT_SPACING,
        minWidth: this.self().COMMIT_SPACING*this.__branches.length,
        allowGrowX: true
      });
      const texts = [];
      texts.push(commitData["tags"]);
      if (commitData["message"]) {
        texts.push(commitData["message"]);
      }
      texts.push(commitData["createdAt"]);
      const hintText = texts.join("<br>");
      const hint = new osparc.ui.hint.Hint(widget, hintText);
      this.__gitGraphInteract.addAt(widget, 0);
      this.__commits.push({
        id: commitData["id"],
        branch,
        commitData,
        widget
      });
      const bgColor = widget.getBackgroundColor();
      widget.addListener("mouseover", e => {
        widget.set({
          backgroundColor: "white",
          cursor: "pointer"
        });
        hint.show();
        // since the widget might be hidden in the scroll area,
        // take mouse's position. It creates a bit of blinking thou
        const native = e.getNativeEvent();
        hint.setLayoutProperties({
          top: native.clientY,
          left: native.clientX
        });
      });
      widget.addListener("mouseout", () => {
        widget.set({
          cursor: "auto"
        });
        hint.exclude();
        if (this.__selectedCommit && this.__selectedCommit.id === commitData["id"]) {
          widget.set({
            backgroundColor: "white"
          });
        } else {
          widget.set({
            backgroundColor: bgColor
          });
        }
      });
      widget.addListener("tap", () => {
        this.setSelection(commitData["id"]);
        this.fireDataEvent("snapshotTap", commitData["id"]);
      });
    },

    resetSelection: function() {
      this.__selectedCommit = null;
      const bgColor = this.getBackgroundColor();
      this.__commits.forEach(commit => {
        commit.widget.set({
          backgroundColor: bgColor
        });
      });
    },

    setSelection: function(snapshotId) {
      this.resetSelection();
      this.__commits.forEach(commit => {
        if (commit.id === snapshotId) {
          commit.widget.set({
            backgroundColor: "white"
          });
          this.__selectedCommit = commit;
        }
      });
    },

    buildExample: function() {
      const master = this.__gitgraph.branch("master");
      this.__commit(master, "Initial commit");
      this.__commit(master, "Some changes");

      const it1 = master.branch("iteration-1");
      this.__commit(it1, "x=1");

      const it2 = master.branch("iteration-2");
      this.__commit(it2, "x=2");

      const it3 = master.branch("iteration-3");
      this.__commit(it3, "x=3");

      this.__commit(master, "Changes after iterations");
    },

    __createBranch: function(lastCommit, fromBranch, name) {
      if (name === undefined) {
        name = "b-"+this.__branches.length.toString();
      }
      const branch = fromBranch ? fromBranch.branch(name) : this.__gitgraph.branch(name);
      branch["lastCommit"] = lastCommit;
      this.__branches.push(branch);
      return branch;
    },

    __getBranch: function(commitData) {
      if (commitData["parents_ids"] === null) {
        const master = this.__createBranch(commitData["id"], null, "master");
        return master;
      }
      const branchFound = this.__branches.find(branch => branch.lastCommit === commitData["parents_ids"][0]);
      if (branchFound) {
        return branchFound;
      }
      const myOnHoldBranch = this.__branches.find(branch => branch.waitingFor === commitData["id"]);
      if (myOnHoldBranch) {
        return myOnHoldBranch;
      }
      const newBranch = this.__createBranch(commitData["id"]);
      return newBranch;
    },

    populateGraph: function(snapshots, currentSnapshot) {
      this.__branches = [];
      this.__parentIDs = [];
      const snapshotsClone = JSON.parse(JSON.stringify(snapshots));
      const sortedSnapshots = snapshotsClone.reverse();
      sortedSnapshots.forEach(snapshot => {
        if ("parents_ids" in snapshot && snapshot["parents_ids"]) {
          snapshot["parents_ids"].forEach(parentID => this.__parentIDs.push(parentID));
        }
      });
      sortedSnapshots.forEach((snapshot, i) => {
        const currentBranch = this.__getBranch(snapshot);
        const snapshotDate = new Date(snapshot["created_at"]);
        const commitData = {
          id: snapshot["id"],
          tags: snapshot["tags"].join(", "),
          message: snapshot["message"],
          createdAt: osparc.utils.Utils.formatDateAndTime(snapshotDate),
          parentsIDs: snapshot["parents_ids"]
        };
        this.__commit(currentBranch, commitData, snapshot["id"] === currentSnapshot["id"]);

        // create as many branches as necessary
        let idx = this.__parentIDs.indexOf(snapshot["id"]);
        while (idx > -1) {
          this.__createBranch(snapshot["id"], currentBranch);
          this.__parentIDs.splice(idx, 1);
          idx = this.__parentIDs.indexOf(snapshot["id"]);
        }
        /*
        // due to this bug https://github.com/nicoespeon/gitgraph.js/issues/270
        // check if more branches need to be created now
        const needBranchedNow = snapshots.filter((snapshotCheck, j) => {
          if (j > i+1) {
            return snapshotCheck["parents_ids"] && snapshotCheck["parents_ids"][0] === snapshot["id"];
          }
          return false;
        });
        needBranchedNow.forEach(snapshotOnHold => {
          const branchOnHold = this.__gitgraph.branch("it-"+this.__branches.length);
          branchOnHold["waitingFor"] = snapshotOnHold["id"];
          this.__branches.push(branchOnHold);
        });
        */
      });
    }
  }
});
