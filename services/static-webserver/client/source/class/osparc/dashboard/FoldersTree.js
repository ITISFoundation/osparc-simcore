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

qx.Class.define("osparc.dashboard.FoldersTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function(currentWorkspaceId) {
    this.__currentWorkspaceId = currentWorkspaceId;

    const workspace = osparc.store.Workspaces.getWorkspace(this.__currentWorkspaceId);
    const workspaceLabel = workspace ? workspace.getName() : "My Workspace";
    const rootData = {
      label: workspaceLabel,
      folderId: null,
      children: [],
      loaded: true,
    };
    const root = qx.data.marshal.Json.createModel(rootData, true);
    this.__populateFolder(root);

    this.base(arguments, root, "label", "children");

    this.setIconPath("icon");
    this.setIconOptions({
      converter(value, _) {
        if (value === "loading") {
          return "@FontAwesome5Solid/circle-notch/12";
        }
        return "@FontAwesome5Solid/folder/12";
      },
    });

    this.__initTree();
  },

  events: {
    "selectionChanged": "qx.event.type.Event" // tap
  },

  members: {
    __currentWorkspaceId:null,

    __initTree: function() {
      const that = this;
      this.setDelegate({
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("icon", "icon", null, item, id);
          c.bindProperty("", "open", {
            converter(value, model, source, target) {
              const isOpen = target.isOpen();
              if (isOpen && !value.getLoaded()) {
                value.setLoaded(true);
                // eslint-disable-next-line no-underscore-dangle
                that.__populateFolder(value);
              }
              return isOpen;
            },
          }, item, id);
        },
      });
    },

    __populateFolder: function(parent) {
      // tree.setAutoScrollIntoView(false);
      parent.getChildren().removeAll();
      // tree.setAutoScrollIntoView(true);

      osparc.store.Folders.getInstance().fetchFolders(parent.getFolderId(), this.__currentWorkspaceId)
        .then(folders => {
          folders.forEach(folder => {
            const folderData = {
              label: folder.getName(),
              folderId: folder.getFolderId(),
              icon: "default",
              loaded: false,
              children: [{
                label: "Loading",
                icon: "loading",
              }]
            };
            parent.getChildren().push(qx.data.marshal.Json.createModel(folderData, true));
          })
        });
    },
  }
});
