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

    this._setLayout(new qx.ui.layout.HBox(20).set({
      alignY: "middle"
    }));
  },

  events: {
    "changeCurrentFolderId": "qx.event.type.Data"
  },

  properties: {
    currentWorkspaceId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      apply: "__applyCurrentFolderId"
    },

    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      apply: "__applyCurrentFolderId"
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
        case "permissions-info": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          })).set({
            paddingRight: 14
          });
          this._addAt(control, 1);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyCurrentFolderId: function() {
      this.__buildBreadcrumbs();
      this.__populatePermissions();
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

    __createFolderButton: function(folder) {
      let folderButton = null;
      if (folder) {
        folderButton = new qx.ui.form.Button(folder.getName(), "@FontAwesome5Solid/folder/14");
      } else {
        const workspaceId = this.getCurrentWorkspaceId();
        if (workspaceId) {
          folderButton = new qx.ui.form.Button(workspaceId, osparc.store.Workspaces.ICON);
        } else {
          folderButton = new qx.ui.form.Button(this.tr("My Workspace"), "@FontAwesome5Solid/home/14");
        }
      }
      folderButton.addListener("execute", () => this.fireDataEvent("changeCurrentFolderId", folder ? folder.getFolderId() : null), this);
      folderButton.set({
        backgroundColor: "transparent",
        textColor: "text",
        gap: 5
      });
      return folderButton;
    },

    __createArrow: function() {
      return new qx.ui.basic.Label("/");
    },

    __populatePermissions: function() {
      const permissionsLayout = this.getChildControl("permissions-info");
      permissionsLayout.removeAll();

      if (this.getCurrentFolderId()) {
        const currentFolder = osparc.store.Folders.getInstance().getFolder(this.getCurrentFolderId());
        const ar = currentFolder.getMyAccessRights();
        const permissions = ar["read"] + ar["write"] + ar["delete"];
        const roleTitle = new qx.ui.basic.Label().set({
          value: osparc.data.Roles.FOLDERS[permissions].label
        });
        permissionsLayout.add(roleTitle);
        permissionsLayout.add(osparc.data.Roles.createRolesFolderInfo(false));
      }
    }
  }
});
