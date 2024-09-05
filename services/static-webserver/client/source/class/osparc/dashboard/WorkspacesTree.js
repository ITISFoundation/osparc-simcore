/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.WorkspacesTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    const rootLabel = "Root";
    const rootWorkspace = this.self().createNewEntry(rootLabel, null);
    const root = qx.data.marshal.Json.createModel(rootWorkspace, true);
    this.__fetchChildren(root);

    this.base(arguments, root, "label", "children");

    this.set({
      openMode: "dbltap",
      decorator: "no-border",
      font: "text-14",
      showLeafs: true,
      paddingLeft: -10,
      hideRoot: true
    });

    this.__initTree();
  },

  events: {
    "selectionChanged": "qx.event.type.Event" // tap
  },

  statics: {
    createNewEntry: function(label, workspaceId) {
      return {
        label,
        workspaceId,
        children: [
          this.self().getLoadingData()
        ],
        loaded: false,
      };
    },

    getLoadingData: function() {
      return {
        workspaceId: -1,
        label: "Loading...",
        children: [],
        icon: "@FontAwesome5Solid/circle-notch/12",
        loaded: false,
      };
    },

    addLoadingChild: function(parentModel) {
      const loadingModel = qx.data.marshal.Json.createModel(this.self().getLoadingData(), true);
      parentModel.getChildren().append(loadingModel);
    },

    removeLoadingChild: function(parent) {
      for (let i = parent.getChildren().getLength() - 1; i >= 0; i--) {
        if (parent.getChildren().toArray()[i].getLabel() === "Loading...") {
          parent.getChildren().splice(i, 1);
        }
      }
    }
  },

  members: {
    __currentWorkspaceId:null,

    __initTree: function() {
      this.setDelegate({
        createItem: () => new osparc.dashboard.WorkspaceTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("workspaceId", "model", null, item, id);
        },
        configureItem: item => {
          item.addListener("tap", () => this.fireDataEvent("selectionChanged", item.getModel()), this);
        },
        sorter: (a, b) => {
          const aLabel = a.getLabel();
          if (aLabel === -1) {
            return 1;
          }
          const bLabel = b.getLabel();
          if (bLabel === -1) {
            return -1;
          }
          return aLabel - bLabel;
        }
      });
    },

    __fetchChildren: function(parentModel) {
      parentModel.setLoaded(true);

      osparc.store.Workspaces.fetchWorkspaces()
        .then(workspaces => {
          this.self().removeLoadingChild(parentModel);
          workspaces.forEach(workspace => {
            const workspaceData = this.self().createNewEntry(workspace.getName(), workspace.getWorkspaceId());
            const workspaceModel = qx.data.marshal.Json.createModel(workspaceData, true);
            parentModel.getChildren().append(workspaceModel);
          });
        })
        .catch(console.error);
    }
  }
});
