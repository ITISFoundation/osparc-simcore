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
 * Widget used for displaying a New Folder in the Study Browser
 *
 */

qx.Class.define("osparc.dashboard.FolderButtonNew", {
  extend: osparc.dashboard.FolderButtonBase,

  construct: function() {
    this.base(arguments);

    this.set({
      appearance: "pb-new"
    });

    this.addListener("changeValue", e => this.__itemSelected(e.getData()), this);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.NEW);

    this.__buildLayout();

    osparc.utils.Utils.setIdToWidget(this, "newFolderButton");
  },

  events: {
    "createFolder": "qx.event.type.Data"
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
          this._add(control, osparc.dashboard.FolderButtonBase.POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label(this.tr("New folder")).set({
            anonymous: true,
            font: "text-14",
            rich: true,
          });
          this._add(control, {
            ...osparc.dashboard.FolderButtonBase.POS.TITLE,
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
        const newFolder = true;
        const folderEditor = new osparc.editor.FolderEditor(newFolder);
        const title = this.tr("New Folder");
        const win = osparc.ui.window.Window.popUpInWindow(folderEditor, title, 300, 120);
        folderEditor.addListener("createFolder", () => {
          const name = folderEditor.getLabel();
          this.fireDataEvent("createFolder", {
            name,
          });
          win.close();
        });
        folderEditor.addListener("cancel", () => win.close());
      }
      this.setValue(false);
    }
  }
});
