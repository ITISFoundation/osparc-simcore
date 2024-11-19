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

    osparc.utils.Utils.setIdToWidget(this, "newWorkspaceButton");
  },

  events: {
    "workspaceCreated": "qx.event.type.Event",
    "workspaceDeleted": "qx.event.type.Event",
    "workspaceUpdated": "qx.event.type.Event",
  },

  members: {
    __itemSelected: function(newVal) {
      if (newVal) {
        const workspaceEditor = new osparc.editor.WorkspaceEditor();
        const title = this.tr("New Workspace");
        const win = osparc.ui.window.Window.popUpInWindow(workspaceEditor, title, 500, 500).set({
          modal: true,
          clickAwayClose: false,
        });
        workspaceEditor.addListener("workspaceCreated", () => this.fireEvent("workspaceCreated"));
        workspaceEditor.addListener("workspaceDeleted", () => this.fireEvent("workspaceDeleted"));
        workspaceEditor.addListener("workspaceUpdated", () => {
          win.close();
          this.fireEvent("workspaceUpdated");
        }, this);
        workspaceEditor.addListener("updateAccessRights", () => this.fireEvent("workspaceUpdated"));
        win.getChildControl("close-button").addListener("tap", () => workspaceEditor.cancel());
        workspaceEditor.addListener("cancel", () => win.close());
      }
      this.setValue(false);
    }
  }
});
