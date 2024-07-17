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
            alignY: "middle",
            alignX: "center",
            padding: 5
          });
          this._add(control, osparc.dashboard.FolderButtonBase.POS.ICON);
          break;
        }
        case "title":
          control = new qx.ui.basic.Label(this.tr("Create New folder")).set({
            anonymous: true,
            font: "text-14",
            alignY: "middle",
            allowGrowX: true,
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
        const renamer = new osparc.widget.Renamer("New Folder", "", this.tr("Create Folder"));
        renamer.addListener("labelChanged", e => {
          renamer.close();
          const folderName = e.getData()["newLabel"];
          this.fireDataEvent("createFolder", folderName);
        }, this);
        renamer.center();
        renamer.open();
      }
      this.setValue(false);
    }
  }
});
