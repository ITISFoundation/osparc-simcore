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
  },

  events: {
    "changeContext": "qx.event.type.Data",
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      apply: "__rebuild"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      apply: "__rebuild"
    }
  },

  members: {
    __rebuild: function() {
      this._removeAll();

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
      return this.__createFolderButton(currentFolder);
    },

    __changeContext: function(workspaceId, folderId) {
      this.set({
        currentWorkspaceId: workspaceId,
        currentFolderId: folderId,
      });
      this.fireDataEvent("changeContext", {
        workspaceId,
        folderId,
      });
    },

    __createRootButton: function() {
      const workspaceId = this.getCurrentWorkspaceId();
      let rootButton = null;
      if (workspaceId) {
        if (workspaceId === -1) {
          rootButton = new qx.ui.form.Button(this.tr("Shared Workspaces"), osparc.store.Workspaces.iconPath());
        } else {
          const workspace = osparc.store.Workspaces.getInstance().getWorkspace(workspaceId);
          rootButton = new qx.ui.form.Button(workspace.getName(), osparc.store.Workspaces.iconPath()).set({
            maxWidth: 200
          });
          workspace.bind("name", rootButton, "label");
        }
      } else {
        rootButton = new qx.ui.form.Button(this.tr("My Workspace"), "@FontAwesome5Solid/home/14");
      }
      rootButton.addListener("execute", () => {
        const folderId = null;
        this.__changeContext(workspaceId, folderId);
      });
      return rootButton;
    },

    __createFolderButton: function(folder) {
      let folderButton = null;
      if (folder) {
        folderButton = new qx.ui.form.Button(folder.getName(), "@FontAwesome5Solid/folder/14").set({
          maxWidth: 200
        });
        folder.bind("name", folderButton, "label");
        folderButton.addListener("execute", () => {
          const workspaceId = this.getCurrentWorkspaceId();
          const folderId = folder ? folder.getFolderId() : null;
          this.__changeContext(workspaceId, folderId);
        }, this);
      } else {
        folderButton = this.__createRootButton();
      }
      folderButton.set({
        backgroundColor: "transparent",
        textColor: "text",
        gap: 5
      });
      return folderButton;
    },

    __createArrow: function() {
      return new qx.ui.basic.Label("/");
    }
  }
});
