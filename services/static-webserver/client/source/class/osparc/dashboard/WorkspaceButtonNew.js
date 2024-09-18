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

/**
 * Widget used for displaying a New Workspace in the Study Browser
 *
 */

qx.Class.define("osparc.dashboard.WorkspaceButtonNew", {
  extend: osparc.dashboard.WorkspaceButtonBase,

  construct: function() {
    this.base(arguments);

    this.set({
      appearance: "pb-new"
    });

    this.addListener("changeValue", e => this.__itemSelected(e.getData()), this);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.NEW);

    const title = this.getChildControl("title");
    title.setValue(this.tr("New Workspace"));

    this.setIcon(osparc.dashboard.CardBase.NEW_ICON);

    this.getChildControl("footer").exclude();
  },

  events: {
    "createWorkspace": "qx.event.type.Data",
    "updateWorkspace": "qx.event.type.Data"
  },

  members: {
    __itemSelected: function(newVal) {
      if (newVal) {
        const workspaceCreator = new osparc.editor.WorkspaceEditor();
        const title = this.tr("New Workspace");
        const win = osparc.ui.window.Window.popUpInWindow(workspaceCreator, title, 300, 200);
        workspaceCreator.addListener("workspaceCreated", e => {
          win.close();
          const newWorkspace = e.getData();
          this.fireDataEvent("createWorkspace", newWorkspace.getWorkspaceId(), this);
          const permissionsView = new osparc.share.CollaboratorsWorkspace(newWorkspace);
          const title2 = qx.locale.Manager.tr("Share Workspace");
          osparc.ui.window.Window.popUpInWindow(permissionsView, title2, 500, 500);
          permissionsView.addListener("updateAccessRights", () => this.fireDataEvent("updateWorkspace", newWorkspace.getWorkspaceId()), this);
        });
        workspaceCreator.addListener("cancel", () => win.close());
      }
      this.setValue(false);
    }
  }
});
