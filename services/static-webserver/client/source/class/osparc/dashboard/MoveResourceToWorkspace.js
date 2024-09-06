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

qx.Class.define("osparc.dashboard.MoveResourceToWorkspace", {
  extend: qx.ui.core.Widget,

  construct: function(studyData, currentWorkspaceId) {
    this.base(arguments);

    this.__studyData = studyData;
    this.__currentWorkspaceId = currentWorkspaceId;

    this._setLayout(new qx.ui.layout.VBox(10));

    this.getChildControl("current-workspace");
    const workspacesTree = this.getChildControl("workspaces-tree");
    this.getChildControl("cancel-btn");
    const moveButton = this.getChildControl("move-btn");

    moveButton.setEnabled(false)
    workspacesTree.addListener("selectionChanged", e => {
      const workspaceId = e.getData();
      moveButton.setEnabled(this.__currentWorkspaceId !== workspaceId);
      this.__selectedWorkspaceId = workspaceId;
    });
    moveButton.addListener("execute", () => {
      this.fireDataEvent("moveToWorkspace", this.__selectedWorkspaceId);
    }, this);
  },

  events: {
    "cancel": "qx.event.type.Event",
    "moveToWorkspace": "qx.event.type.Data"
  },

  members: {
    __studyData: null,
    __currentWorkspaceId: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "current-workspace": {
          const workspace = osparc.store.Workspaces.getWorkspace(this.__currentWorkspaceId);
          const currentWorkspaceName = workspace ? workspace.getName() : "My Workspace";
          control = new qx.ui.basic.Label(this.tr("Current location: ") + currentWorkspaceName);
          this._add(control);
          break;
        }
        case "workspaces-tree":
          control = new osparc.dashboard.WorkspacesTree();
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
