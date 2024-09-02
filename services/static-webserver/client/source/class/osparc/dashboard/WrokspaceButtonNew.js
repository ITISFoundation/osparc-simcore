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

    this.__buildLayout();
  },

  events: {
    "createWorkspace": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "icon": {
          control = new qx.ui.basic.Image().set({
            source: osparc.dashboard.CardBase.NEW_ICON + "26",
            anonymous: true,
            height: 40,
            padding: 5
          });
          this._add(control, osparc.dashboard.WorkspaceButtonBase.POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label(this.tr("New workspace")).set({
            anonymous: true,
            font: "text-14",
            rich: true,
          });
          this._add(control, {
            ...osparc.dashboard.WorkspaceButtonBase.POS.TITLE,
            ...{rowSpan: 2}
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("icon");
      this.getChildControl("title");
    },

    __itemSelected: function(newVal) {
      if (newVal) {
        const newWorkspace = true;
        const workspaceEditor = new osparc.editor.WorkspaceEditor(newWorkspace);
        const title = this.tr("New Workspace");
        const win = osparc.ui.window.Window.popUpInWindow(workspaceEditor, title, 300, 200);
        workspaceEditor.addListener("createWorkspace", () => {
          const name = workspaceEditor.getLabel();
          const description = workspaceEditor.getDescription();
          this.fireDataEvent("createWorkspace", {
            name,
            description
          });
          win.close();
        });
        workspaceEditor.addListener("cancel", () => win.close());
      }
      this.setValue(false);
    }
  }
});
