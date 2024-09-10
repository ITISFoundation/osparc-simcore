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

qx.Class.define("osparc.dashboard.ContainerHeader", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(20).set({
      alignY: "middle"
    }));
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentWorkspaceId",
      apply: "__buildBreadcrumbs"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      apply: "__buildBreadcrumbs"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "breadcrumbs-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignY: "middle"
          }));
          this._addAt(control, 0, {flex: 1});
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildBreadcrumbs: function() {
      const breadcrumbsLayout = this.getChildControl("breadcrumbs-layout");
      breadcrumbsLayout.removeAll();

      if (this.getCurrentFolderId()) {
        const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
        this.__createUpstreamButtons(currentFolder);
      }

      const currentFolderButton = this.__createCurrentFolderButton();
      if (currentFolderButton) {
        breadcrumbsLayout.add(currentFolderButton);
      }
    },

    __createUpstreamButtons: function(childFolder) {
      if (childFolder) {
        const breadcrumbsLayout = this.getChildControl("breadcrumbs-layout");
        const parentFolder = osparc.store.Folders.getInstance().getFolder(childFolder.getParentId());
        if (parentFolder) {
          breadcrumbsLayout.addAt(this.__createArrow(), 0);
          const upstreamButton = this.__createFolderButton(parentFolder);
          breadcrumbsLayout.addAt(upstreamButton, 0);
          this.__createUpstreamButtons(parentFolder);
        } else {
          breadcrumbsLayout.addAt(this.__createArrow(), 0);
          const homeButton = this.__createFolderButton();
          breadcrumbsLayout.addAt(homeButton, 0);
        }
      }
    },

    __createCurrentFolderButton: function() {
      const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
      return this.__createFolderButton(currentFolder);
    },

    __createRootButton: function(workspaceId) {
      let rootButton = null;
      if (workspaceId) {
        if (workspaceId === -1) {
          rootButton = new qx.ui.form.Button(this.tr("Shared Workspaces"), osparc.store.Workspaces.iconPath());
        } else {
          const workspace = osparc.store.Workspaces.getWorkspace(workspaceId);
          rootButton = new qx.ui.form.Button(workspace.getName(), osparc.store.Workspaces.iconPath());
        }
        rootButton.addListener("execute", () => this.set({
          currentWorkspaceId: workspaceId,
          currentFolderId: null,
        }));
      } else {
        rootButton = new qx.ui.form.Button(this.tr("My Workspace"), "@FontAwesome5Solid/home/14");
        rootButton.addListener("execute", () => this.set({
          currentWorkspaceId: null,
          currentFolderId: null,
        }));
      }
      return rootButton;
    },

    __createFolderButton: function(folder) {
      let folderButton = null;
      if (folder) {
        folderButton = new qx.ui.form.Button(folder.getName(), "@FontAwesome5Solid/folder/14");
        folderButton.addListener("execute", () => this.fireDataEvent("changeCurrentFolderId", folder ? folder.getFolderId() : null), this);
      } else {
        const workspaceId = this.getCurrentWorkspaceId();
        folderButton = this.__createRootButton(workspaceId);
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
