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

    this.__models = [];

    this.base(arguments, rootModel, "label", "children");

    this.set({
      openMode: "dbltap",
      decorator: "no-border",
      font: "text-14",
      hideRoot: true,
      contentPadding: 0,
      padding: 0,
    });

    this.__addMyWorkspace(rootModel);
    this.__addSharedWorkspaces(rootModel);

    this.__initTree();

    // preselect "My Workspace"
    this.contextChanged("studiesAndFolders");

    osparc.store.Folders.getInstance().addListener("folderAdded", e => {
      const folder = e.getData();
      this.__folderAdded(folder);
    }, this);

    osparc.store.Folders.getInstance().addListener("folderRemoved", e => {
      const folder = e.getData();
      this.__folderRemoved(folder);
    }, this);

    osparc.store.Folders.getInstance().addListener("folderMoved", e => {
      const {
        folder,
        oldParentFolderId,
      } = e.getData();
      this.__folderRemoved(folder, oldParentFolderId);
      this.__folderAdded(folder);
    }, this);

    osparc.store.Workspaces.getInstance().addListener("workspaceAdded", e => {
      const workspace = e.getData();
      this.__addWorkspace(workspace);
    }, this);

    osparc.store.Workspaces.getInstance().addListener("workspaceRemoved", e => {
      const workspace = e.getData();
      this.__workspaceRemoved(workspace);
    }, this);

    this.getSelection().addListener("change", () => {
      const selection = this.getSelection();
      if (selection.getLength() > 0) {
        const item = selection.getItem(0);
        const workspaceId = item.getWorkspaceId();
        const folderId = item.getFolderId();
        this.fireDataEvent("locationChanged", {
          workspaceId,
          folderId,
        });
      }
    }, this);
  },

  events: {
    "openChanged": "qx.event.type.Event",
    "locationChanged": "qx.event.type.Data",
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
    },
  },

  members: {
    __models: null,

    __initTree: function() {
      const that = this;
      this.setDelegate({
        createItem: () => new osparc.dashboard.WorkspacesAndFoldersTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("", "open", {
            converter(value, _model, _source, target) {
              const isOpen = target.isOpen();
              if (isOpen) {
                // eslint-disable-next-line no-underscore-dangle
                that.__populateFolder(value, value.getWorkspaceId(), value.getFolderId())
                  .then(folderModels => {
                    // load next level too
                    folderModels.forEach(folderModel => {
                      // eslint-disable-next-line no-underscore-dangle
                      that.__populateFolder(folderModel, folderModel.getWorkspaceId(), folderModel.getFolderId());
                    })
                  });
              }
              that.fireEvent("openChanged");
              return isOpen;
            },
          }, item, id);
        },
        configureItem: item => {
          item.addListener("changeModel", e => {
            const model = e.getData();
            osparc.utils.Utils.setIdToWidget(item, `workspacesAndFoldersTreeItem_${model.getWorkspaceId()}_${model.getFolderId()}`);
          })
        }
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

    __createItemData: function(label, icon, workspaceId, folderId) {
      return {
        label,
        icon,
        workspaceId,
        folderId,
        loaded: false,
        children: [{
          label: "Loading...",
        }],
      };
    },

    __addMyWorkspace: function(rootModel) {
      const workspaceId = null;
      const folderId = null;
      const myWorkspaceData = this.__createItemData(
        "My Workspace",
        "home",
        workspaceId,
        folderId,
      );
      const myWorkspaceModel = qx.data.marshal.Json.createModel(myWorkspaceData, true);
      this.__models.push(myWorkspaceModel);
      rootModel.getChildren().append(myWorkspaceModel);

      // load next level too
      this.__populateFolder(myWorkspaceModel, workspaceId, folderId);
    },

    __addSharedWorkspaces: function(rootModel) {
      const workspaceId = -1;
      const folderId = null;
      const sharedWorkspaceData = this.__createItemData(
        "Shared Workspaces",
        "shared",
        workspaceId,
        folderId,
      );
      const sharedWorkspaceModel = qx.data.marshal.Json.createModel(sharedWorkspaceData, true);
      this.__models.push(sharedWorkspaceModel);
      rootModel.getChildren().append(sharedWorkspaceModel);

      osparc.store.Workspaces.getInstance().fetchWorkspaces()
        .then(workspaces => {
          sharedWorkspaceModel.setLoaded(true);
          sharedWorkspaceModel.getChildren().removeAll();
          workspaces.forEach(workspace => {
            this.__addWorkspace(workspace);
          });
        })
        .catch(console.error);
    },

    __addWorkspace: function(workspace) {
      const workspaceId = workspace.getWorkspaceId();
      const folderId = null;
      const workspaceData = this.__createItemData(
        "",
        "shared",
        workspaceId,
        folderId,
      );
      const workspaceModel = qx.data.marshal.Json.createModel(workspaceData, true);
      this.__models.push(workspaceModel);
      workspace.bind("name", workspaceModel, "label");

      const sharedWorkspaceModel = this.__getModel(-1, null);
      sharedWorkspaceModel.getChildren().append(workspaceModel);
      sharedWorkspaceModel.getChildren().sort(((a, b) => {
        return a.getLabel().localeCompare(b.getLabel());
      }));

      // load next level too
      this.__populateFolder(workspaceModel, workspace.getWorkspaceId(), null);
    },

    __workspaceRemoved: function(workspace) {
      // remove it from the tree
      const sharedWorkspaceModel = this.__getModel(-1, null);
      const idx = sharedWorkspaceModel.getChildren().toArray().findIndex(w => workspace.getWorkspaceId() === w.getWorkspaceId());
      if (idx > -1) {
        sharedWorkspaceModel.getChildren().removeAt(idx);
      }

      // remove it from the cached models
      const modelFound = this.__getModel(workspace.getWorkspaceId(), null);
      if (modelFound) {
        const index = this.__models.indexOf(modelFound);
        if (index > -1) { // only splice array when item is found
          this.__models.splice(index, 1); // 2nd parameter means remove one item only
        }
      }
    },

    __addFolder: function(folder, parentModel) {
      const workspaceId = folder.getWorkspaceId();
      const folderData = this.__createItemData(
        "",
        workspaceId ? "shared" : "folder",
        workspaceId,
        folder.getFolderId(),
      );
      const folderModel = qx.data.marshal.Json.createModel(folderData, true);
      this.__models.push(folderModel);
      folder.bind("name", folderModel, "label");
      parentModel.getChildren().append(folderModel);
      parentModel.getChildren().sort(((a, b) => {
        return a.getLabel().localeCompare(b.getLabel());
      }));
      return folderModel;
    },

    __populateFolder: function(model, workspaceId, folderId) {
      if (model.getLoaded()) {
        return new Promise(resolve => resolve(model.getChildren()));
      }
      return osparc.store.Folders.getInstance().fetchFolders(folderId, workspaceId)
        .then(folders => {
          model.setLoaded(true);
          model.getChildren().removeAll();
          const newFolderModels = [];
          folders.forEach(folder => {
            newFolderModels.push(this.__addFolder(folder, model));
          });
          return newFolderModels;
        });
    },

    __getModel: function(workspaceId, folderId) {
      return this.__models.find(mdl => mdl.getWorkspaceId() === workspaceId && mdl.getFolderId() === folderId);
    },

    __folderAdded: function(folder) {
      const parentModel = this.__getModel(folder.getWorkspaceId(), folder.getParentFolderId());
      if (parentModel) {
        this.__addFolder(folder, parentModel);
      }
    },

    __folderRemoved: function(folder, oldParentFolderId) {
      // eslint-disable-next-line no-negated-condition
      const parentModel = this.__getModel(folder.getWorkspaceId(), oldParentFolderId !== undefined ? oldParentFolderId : folder.getParentFolderId());
      if (parentModel) {
        const idx = parentModel.getChildren().toArray().findIndex(c => folder.getWorkspaceId() === c.getWorkspaceId() && folder.getFolderId() === c.getFolderId());
        if (idx > -1) {
          parentModel.getChildren().removeAt(idx);
        }
      }

      if (oldParentFolderId === undefined) {
        // it was removed, not moved
        // remove it from the cached models
        const modelFound = this.__getModel(folder.getWorkspaceId(), folder.getFolderId());
        if (modelFound) {
          const index = this.__models.indexOf(modelFound);
          if (index > -1) { // only splice array when item is found
            this.__models.splice(index, 1); // 2nd parameter means remove one item only
          }
        }
      }
    },

    contextChanged: function(context) {
      const selection = this.getSelection();
      if (selection) {
        selection.removeAll();
      }
      if (context === "studiesAndFolders" || context === "workspaces") {
        const workspaceId = context === "workspaces" ? -1 : this.getCurrentWorkspaceId();
        const folderId = this.getCurrentFolderId();
        const locationModel = this.__getModel(workspaceId, folderId);
        if (locationModel) {
          selection.push(locationModel);
        }
      }
    },
  }
});
