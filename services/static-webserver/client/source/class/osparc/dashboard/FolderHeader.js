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

    this._setLayout(new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    }));

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
        const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
        this.__createUpstreamButtons(currentFolder);

        const currentFolderButton = this.__createCurrentFolderButton();
        if (currentFolderButton) {
          this._add(currentFolderButton);
        }
      }
    },

    __createUpstreamButtons: function(childFolder) {
      if (childFolder) {
        const parentFolder = osparc.store.Folders.getInstance().getFolder(childFolder.getParentId());
        if (parentFolder) {
          this._addAt(this.__createArrow(), 0);
          const upstreamButton = this.__createFolderButton(parentFolder);
          this._addAt(upstreamButton, 0);
          this.__createUpstreamButtons(parentFolder);
        } else {
          this._addAt(this.__createArrow(), 0);
          const homeButton = this.__createFolderButton();
          this._addAt(homeButton, 0);
        }
      }
    },

    __createCurrentFolderButton: function() {
      const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
      if (currentFolder) {
        const currentFolderButton = this.__createFolderButton(currentFolder);
        return currentFolderButton;
      }
      return null;
    },

    __createFolderButton: function(folder) {
      let folderButton = null;
      if (folder) {
        folderButton = new qx.ui.form.Button(folder.getName(), "@FontAwesome5Solid/folder/14");
        folderButton.addListener("execute", () => this.fireDataEvent("changeCurrentFolderId", folder.getId()), this);
      } else {
        folderButton = new qx.ui.form.Button(this.tr("Home"), "@FontAwesome5Solid/home/14");
        folderButton.addListener("execute", () => this.fireDataEvent("changeCurrentFolderId", null), this);
      }
      folderButton.set({
        backgroundColor: "transparent",
        font: "text-14",
        textColor: "text",
        gap: 5,
      });
      return folderButton;
    },

    __createArrow: function() {
      return new qx.ui.basic.Label("->");
    }
  }
});
