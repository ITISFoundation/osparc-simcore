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
    "createWorkspace": "qx.event.type.Data"
  },

  members: {
    __itemSelected: function(newVal) {
      if (newVal) {
        const workspaceEditor = new osparc.editor.WorkspaceEditor(true);
        const title = this.tr("New Workspace");
        const win = osparc.ui.window.Window.popUpInWindow(workspaceEditor, title, 300, 200);
        workspaceEditor.addListener("createWorkspace", () => {
          const newWorkspaceData = {
            name: workspaceEditor.getLabel(),
            description: workspaceEditor.getDescription(),
            thumbnail: workspaceEditor.getThumbnail(),
          };
          osparc.store.Workspaces.postWorkspace(newWorkspaceData)
            .then(newWorkspace => {
              this.fireDataEvent("createWorkspace");
              const permissionsView = new osparc.share.CollaboratorsWorkspace(newWorkspace);
              permissionsView.addListener("updateAccessRights", e => {
                const updatedData = e.getData();
                console.log(updatedData);
              }, this);
            })
            .catch(console.error)
            .finally(() => win.close());
          
            name,
            description
          });
          
        });
        workspaceEditor.addListener("cancel", () => win.close());
      }
      this.setValue(false);
    }
  }
});
