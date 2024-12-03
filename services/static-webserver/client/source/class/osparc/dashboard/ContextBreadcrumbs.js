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

qx.Class.define("osparc.dashboard.ContextBreadcrumbs", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    }));

    osparc.store.Store.getInstance().addListener("changeStudyBrowserContext", () => this.__rebuild(), this);
  },

  events: {
    "locationChanged": "qx.event.type.Data",
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentWorkspaceId",
      apply: "__rebuild"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      apply: "__rebuild"
    }
  },

  members: {
    __rebuild: function() {
      this._removeAll();

      const currentContext = osparc.store.Store.getInstance().getStudyBrowserContext();
      if (currentContext !== "studiesAndFolders") {
        return;
      }

      if (this.getCurrentFolderId()) {
        const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
        this.__createUpstreamButtons(currentFolder);
      }

      const currentFolderButton = this.__createCurrentFolderButton();
      if (currentFolderButton) {
        this._add(currentFolderButton);
      }
    },

    __createUpstreamButtons: function(childFolder) {
      if (childFolder) {
        const parentFolder = osparc.store.Folders.getInstance().getFolder(childFolder.getParentFolderId());
        if (parentFolder) {
          this._addAt(this.__createArrow(), 0);
          const upstreamButton = this.__createFolderButton(parentFolder);
          if (upstreamButton) {
            this._addAt(upstreamButton, 0);
          }
          this.__createUpstreamButtons(parentFolder);
        } else {
          this._addAt(this.__createArrow(), 0);
        }
      }
    },

    __createCurrentFolderButton: function() {
      const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
      return this.__createFolderButton(currentFolder);
    },

    __changeFolder: function(folderId) {
      const workspaceId = this.getCurrentWorkspaceId();
      this.set({
        currentWorkspaceId: workspaceId,
        currentFolderId: folderId,
      });
      this.fireDataEvent("locationChanged", {
        workspaceId,
        folderId,
      });
    },

    __createFolderButton: function(folder) {
      if (folder) {
        const folderButton = new qx.ui.form.Button(folder.getName()).set({
          maxWidth: 200
        });
        folder.bind("name", folderButton, "label");
        folderButton.addListener("execute", () => {
          const folderId = folder ? folder.getFolderId() : null;
          this.__changeFolder(folderId);
        }, this);
        folderButton.set({
          backgroundColor: "transparent",
          textColor: "text",
          gap: 5
        });
        return folderButton;
      }
      return null;
    },

    __createArrow: function() {
      return new qx.ui.basic.Label("/");
    }
  }
});
