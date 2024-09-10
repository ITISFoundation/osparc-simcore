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

qx.Class.define("osparc.dashboard.WorkspacesAndFoldersTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    const treeName = "WorkspacesAndFoldersTree";
    const rootData = {
      label: treeName,
      children: [],
      loaded: true,
    };
    const rootModel = qx.data.marshal.Json.createModel(rootData, true);

    this.base(arguments, rootModel, "label", "children");

    this.set({
      openMode: "dbltap",
      decorator: "no-border",
      font: "text-14",
      hideRoot: true,
      paddingLeft: -10,
      paddingTop: -10,
    });

    this.__addMyWorkspace(rootModel);
    this.__addSharedWorkspaces(rootModel);

    this.__initTree();
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentWorkspaceId",
      // apply: "__applyCurrentWorkspaceId"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      // apply: "__resetAndReloadAll"
    },
  },

  members: {
    __initTree: function() {
      const that = this;
      this.setDelegate({
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("", "open", {
            converter(value, model, source, target) {
              const isOpen = target.isOpen();
              if (isOpen && !value.getLoaded()) {
                // eslint-disable-next-line no-underscore-dangle
                that.__populateFolder(value, value.getWorkspaceId(), value.getFolderId());
              }
              return isOpen;
            },
          }, item, id);
        },
        configureItem: item => {
          item.addListener("tap", () => {
            this.set({
              currentWorkspaceId: item.getModel().getWorkspaceId(),
              currentFolderId: item.getModel().getFolderId(),
            })
          }, this);
        },
      });

      this.setIconPath("icon");
      this.setIconOptions({
        converter(value) {
          if (value === "shared") {
            return osparc.store.Workspaces.iconPath(18);
          } else if (value === "home") {
            return "@FontAwesome5Solid/home/16";
          }
          return "@FontAwesome5Solid/folder/16";
        },
      });
    },

    __addMyWorkspace: function(rootModel) {
      const myWorkspaceData = {
        label: "My Workspace",
        icon: "home",
        workspaceId: null,
        folderId: null,
        loaded: false,
        children: [{
          label: "Loading...",
        }],
      }
      const myWorkspaceModel = qx.data.marshal.Json.createModel(myWorkspaceData, true);
      rootModel.getChildren().append(myWorkspaceModel);
    },

    __addSharedWorkspaces: function(rootModel) {
      const sharedWorkspaceData = {
        label: "Shared Workspace",
        icon: "shared",
        workspaceId: -1,
        folderId: null,
        loaded: true,
        children: [],
      }
      const sharedWorkspaceModel = qx.data.marshal.Json.createModel(sharedWorkspaceData, true);
      rootModel.getChildren().append(sharedWorkspaceModel);

      osparc.store.Workspaces.fetchWorkspaces()
        .then(workspaces => {
          workspaces.forEach(workspace => {
            const workspaceData = {
              label: workspace.getName(),
              icon: "shared",
              workspaceId: workspace.getWorkspaceId(),
              folderId: null,
              loaded: false,
              children: [{
                label: "Loading...",
              }],
            };
            const workspaceModel = qx.data.marshal.Json.createModel(workspaceData, true);
            sharedWorkspaceModel.getChildren().append(workspaceModel);
          });
        })
        .catch(console.error);
    },

    __populateFolder: function(model, workspaceId, folderId) {
      osparc.store.Folders.getInstance().fetchFolders(folderId, workspaceId)
        .then(folders => {
          model.setLoaded(true);
          model.getChildren().removeAll();
          folders.forEach(folder => {
            const folderData = {
              label: folder.getName(),
              icon: workspaceId ? "shared" : "folder",
              workspaceId,
              folderId: folder.getFolderId(),
              loaded: false,
              children: [{
                label: "Loading...",
              }]
            };
            model.getChildren().push(qx.data.marshal.Json.createModel(folderData, true));
          });
        });
    }
  }
});
