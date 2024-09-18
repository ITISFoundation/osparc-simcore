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
    const rootData = {
      label: "Workspaces",
      icon: "default",
      workspaceId: -1,
      children: [],
      loaded: true,
    };
    const root = qx.data.marshal.Json.createModel(rootData, true);
    this.__fetchChildren(root);

    this.base(arguments, root, "label", "children");

    this.set({
      openMode: "dbltap",
      decorator: "no-border",
      font: "text-14",
      showLeafs: true,
      paddingLeft: -10,
    });

    this.__initTree();
  },

  events: {
    "selectionChanged": "qx.event.type.Event" // tap
  },

  members: {
    __currentWorkspaceId:null,

    __initTree: function() {
      this.setDelegate({
        createItem: () => new qx.ui.tree.VirtualTreeItem(),
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

      this.setIconPath("icon");
      this.setIconOptions({
        converter(value) {
          if (value === "shared") {
            return osparc.store.Workspaces.iconPath(16);
          }
          return "@FontAwesome5Solid/folder/14";
        },
      });
    },

    __fetchChildren: function(parent) {
      parent.setLoaded(true);

      const myWorkspaceData = {
        label: "My Workspace",
        icon: "default",
        workspaceId: null,
        loaded: true,
      };
      const myWorkspaceModel = qx.data.marshal.Json.createModel(myWorkspaceData, true);
      parent.getChildren().append(myWorkspaceModel);

      osparc.store.Workspaces.getInstance().fetchWorkspaces()
        .then(workspaces => {
          workspaces.forEach(workspace => {
            const workspaceData = {
              label: workspace.getName(),
              icon: "shared",
              workspaceId: workspace.getWorkspaceId(),
              loaded: true,
            };
            const workspaceModel = qx.data.marshal.Json.createModel(workspaceData, true);
            parent.getChildren().append(workspaceModel);
          });
        })
        .catch(console.error);
    }
  }
});
