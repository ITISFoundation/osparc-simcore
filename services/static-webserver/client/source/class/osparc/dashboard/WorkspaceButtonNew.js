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

    this.getChildControl("header").set({
      opacity: 1
    });
    this.getChildControl("footer").exclude();
  },

  events: {
    "workspaceCreated": "qx.event.type.Data",
    "workspaceUpdated": "qx.event.type.Data"
  },

  members: {
    __itemSelected: function(newVal) {
      if (newVal) {
        const workspaceEditor = new osparc.editor.WorkspaceEditor();
        const title = this.tr("New Workspace");
        const win = osparc.ui.window.Window.popUpInWindow(workspaceEditor, title, 500, 500);
        workspaceEditor.addListener("workspaceCreated", e => {
          const newWorkspace = e.getData();
          this.fireDataEvent("workspaceCreated", newWorkspace.getWorkspaceId(), this);
        });
        workspaceEditor.addListener("updateAccessRights", () => this.fireDataEvent("workspaceUpdated", workspaceEditor.getWorkspace()), this);
        workspaceEditor.addListener("cancel", () => win.close());
      }
      this.setValue(false);
    }
  }
});
