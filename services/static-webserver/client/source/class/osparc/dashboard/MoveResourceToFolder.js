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

qx.Class.define("osparc.dashboard.MoveResourceToFolder", {
  extend: qx.ui.core.Widget,

  construct: function(currentFolderId, currentWorkspaceId) {
    this.base(arguments);

    this.__currentFolderId = currentFolderId;
    this.__currentWorkspaceId = currentWorkspaceId;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("current-folder");
    const foldersTree = this.getChildControl("folders-tree");
    this.getChildControl("cancel-btn");
    const moveButton = this.getChildControl("move-btn");

    moveButton.setEnabled(false)
    foldersTree.addListener("selectionChanged", e => {
      const folderId = e.getData();
      moveButton.setEnabled(this.__currentFolderId !== folderId);
      this.__selectedFolderId = folderId;
    });
    moveButton.addListener("execute", () => {
      this.fireDataEvent("moveToFolder", this.__selectedFolderId);
    });
  },

  events: {
    "cancel": "qx.event.type.Event",
    "moveToFolder": "qx.event.type.Data"
  },

  members: {
    __currentFolderId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "current-folder": {
          const folder = osparc.store.Folders.getInstance().getFolder(this.__currentFolderId);
          const currentFolderName = folder ? folder["name"] : "Home";
          control = new qx.ui.basic.Label(this.tr("Current location: ") + currentFolderName);
          this._add(control);
          break;
        }
        case "folders-tree":
          control = new osparc.dashboard.FoldersTree(this.__currentWorkspaceId);
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
