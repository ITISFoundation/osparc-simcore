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

qx.Class.define("osparc.dashboard.MoveResourceTo", {
  extend: qx.ui.core.Widget,

  construct: function(currentWorkspaceId, currentFolderId) {
    this.base(arguments);

    this.__currentWorkspaceId = currentWorkspaceId;
    this.__currentFolderId = currentFolderId;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("current-location");

    const workspacesAndFoldersTree = this.getChildControl("workspaces-and-folders-tree");
    this.getChildControl("cancel-btn");
    const moveButton = this.getChildControl("move-btn");

    moveButton.setEnabled(false);
    workspacesAndFoldersTree.getSelection().addListener("change", () => {
      const selection = workspacesAndFoldersTree.getSelection();
      if (selection.getLength() > 0) {
        const item = selection.getItem(0);
        this.__selectedWorkspaceId = item.getWorkspaceId();
        this.__selectedFolderId = item.getFolderId();
        if (this.__selectedWorkspaceId === -1) {
          // "Shared Workspaces"
          moveButton.setEnabled(false);
        } else {
          // In principle, valid location
          // disable if it's the current location
          moveButton.setEnabled(this.__currentWorkspaceId !== this.__selectedWorkspaceId || this.__currentFolderId !== this.__selectedFolderId);
        }
      }
    }, this);
    moveButton.addListener("execute", () => {
      this.fireDataEvent("moveTo", {
        workspaceId: this.__selectedWorkspaceId,
        folderId: this.__selectedFolderId,
      });
    }, this);
  },

  events: {
    "cancel": "qx.event.type.Event",
    "moveTo": "qx.event.type.Data"
  },

  members: {
    __currentWorkspaceId: null,
    __currentFolderId: null,
    __selectedWorkspaceId: null,
    __selectedFolderId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "current-location": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          const intro = new qx.ui.basic.Label(this.tr("Current location"));
          control.add(intro);
          const workspace = osparc.store.Workspaces.getInstance().getWorkspace(this.__currentWorkspaceId);
          const workspaceText = workspace ? workspace.getName() : "My Workspace";
          const workspaceLabel = new qx.ui.basic.Label(this.tr("- Workspace: ") + workspaceText);
          control.add(workspaceLabel);
          const folder = osparc.store.Folders.getInstance().getFolder(this.__currentFolderId);
          if (folder) {
            const folderText = folder.getName();
            const folderLabel = new qx.ui.basic.Label(this.tr("- Folder: ") + folderText);
            control.add(folderLabel);
          }
          this._add(control);
          break;
        }
        case "workspaces-and-folders-tree":
          control = new osparc.dashboard.WorkspacesAndFoldersTree();
          this._add(control, {
            flex: 1
          });
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "cancel-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            appearance: "form-button-text"
          });
          control.addListener("execute", () => this.fireEvent("cancel"), this);
          buttons.add(control);
          break;
        }
        case "move-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Move")).set({
            appearance: "form-button"
          });
          buttons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __getUpstreamFolders: function(childFolder, folderIds = []) {
      if (childFolder) {
        folderIds.unshift(childFolder.getFolderId());
        const parentFolder = osparc.store.Folders.getInstance().getFolder(childFolder.getParentFolderId());
        this.__getUpstreamFolders(parentFolder, folderIds);
      }
    }
  }
});
