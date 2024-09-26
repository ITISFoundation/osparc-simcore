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

qx.Class.define("osparc.dashboard.MoveResource", {
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
        moveButton.setEnabled(this.__currentWorkspaceId !== this.__selectedWorkspaceId || this.__currentFolderId !== this.__selectedFolderId);
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
          const workspace = osparc.store.Workspaces.getInstance().getWorkspace(this.__currentWorkspaceId);
          let currentLocation = workspace ? workspace.getName() : "My Workspace";
          const folder = osparc.store.Folders.getInstance().getFolder(this.__currentFolderId);
          if (folder) {
            // OM intermediate folders missing
            currentLocation += " / " + folder.getName()
          }
          control = new qx.ui.basic.Label(this.tr("Current location: ") + currentLocation);
          this._add(control);
          break;
        }
        case "workspaces-and-folders-tree":
          control = new osparc.dashboard.WorkspacesAndFoldersTree();
          this._add(control);
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
    }
  }
});
