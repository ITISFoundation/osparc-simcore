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

qx.Class.define("osparc.dashboard.FolderHeader", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    this.bind("currentFolderId", this, "visibility", {
      converter: currentFolderId => currentFolderId ? "visible" : "excluded"
    });
  },

  events: {
    "changeCurrentFolderId": "qx.event.type.Data"
  },

  properties: {
    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      apply: "__applyCurrentFolderId"
    }
  },

  members: {
    __applyCurrentFolderId: function(currentFolderId) {
      this._removeAll();

      if (currentFolderId) {
        const upstreamButton = this.__createUpstreamButton();
        if (upstreamButton) {
          this._add(upstreamButton);

          this._add(new qx.ui.basic.Label(">"));
        }

        const currentFolderButton = this.__createCurrentFolderButton();
        if (currentFolderButton) {
          this._add(currentFolderButton);
        }
      }
    },

    __createUpstreamButton: function() {
      const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
      if (currentFolder) {
        const parentFolder = osparc.store.Folders.getInstance().getFolder(currentFolder.getParentId());
        if (parentFolder) {
          const upstreamButton = new qx.ui.form.Button(parentFolder.getName(), "@FontAwesome5Solid/folder/16");
          upstreamButton.addListener("execute", () => this.fireDataEvent("changeCurrentFolderId", parentFolder.getId()), this);
          return upstreamButton;
        }
        const homeButton = new qx.ui.form.Button(this.tr("Home", "@FontAwesome5Solid/home/16"));
        homeButton.addListener("execute", () => this.fireDataEvent("changeCurrentFolderId", null), this);
        return homeButton;
      }
      return null;
    },

    __createCurrentFolderButton: function() {
      const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
      if (currentFolder) {
        const currentFolderButton = new qx.ui.form.Button(currentFolder.getName(), "@FontAwesome5Solid/folder/16");
        return currentFolderButton;
      }
      return null;
    }
  }
});
