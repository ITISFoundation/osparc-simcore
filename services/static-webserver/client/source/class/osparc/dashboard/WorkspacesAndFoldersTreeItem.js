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

qx.Class.define("osparc.dashboard.WorkspacesAndFoldersTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);

    this.set({
      indent: 12, // defaults to 19,
      decorator: "rounded",
      padding: 2,
      maxWidth: osparc.dashboard.ResourceBrowserBase.SIDE_SPACER_WIDTH - 12,
    });

    this.setNotHoveredStyle();
    this.__attachEventHandlers();

    this.__attachDragHandlers();
    this.__attachDropHandlers();
  },

  members: {
    __attachEventHandlers: function() {
      this.addListener("mouseover", () => {
        this.setHoveredStyle();
      });
      this.addListener("mouseout", () => {
        this.setNotHoveredStyle();
      });
    },

    setHoveredStyle: function() {
      osparc.utils.Utils.addBorder(this, 1, qx.theme.manager.Color.getInstance().resolve("text"));
    },

    setNotHoveredStyle: function() {
      osparc.utils.Utils.hideBorder(this);
    },

    __getFolder: function() {
      const folderId = this.getModel().getFolderId();
      if (folderId === null) {
        return null;
      }
      return osparc.store.Folders.getInstance().getFolder(folderId);
    },

    __attachDragHandlers: function() {
      this.setDraggable(true);

      this.addListener("dragstart", e => {
        const folder = this.__getFolder();
        // only folders can be dragged
        if (folder == null) {
          e.preventDefault();
          return;
        }

        // make it semi transparent while being dragged
        this.setOpacity(0.2);

        osparc.dashboard.DragWidget.dragStartFolder(e, folder);
      });

      this.addListener("dragend", () => {
        // bring back opacity after drag
        this.setOpacity(1);

        osparc.dashboard.DragWidget.dragEnd();
      });
    },

    __attachDropHandlers: function() {
      this.setDroppable(true);

      this.addListener("dragover", e => {
        let compatible = false;
        if (e.supportsType("osparc-moveStudy")) {
          const studyData = e.getData("osparc-moveStudy")["studyDataOrigin"];
          // Compatibility checks:
          // - My workspace
          //   - None
          // - Shared workspace
          //   - write access on workspace
          const workspaceId = studyData["workspaceId"];
          if (workspaceId) {
            const workspace = osparc.store.Workspaces.getInstance().getWorkspace(workspaceId);
            if (workspace) {
              compatible = workspace.getMyAccessRights()["write"];
            }
          } else {
            compatible = true;
          }
        } else if (e.supportsType("osparc-moveFolder")) {
          const folder = this.__getFolder();
          if (folder == null) {
            e.preventDefault();
            return;
          }

          // Compatibility checks:
          // - It's not the same folder
          // - My workspace
          //   - None
          // - Shared workspace
          //   - write access on workspace
          const folderOrigin = e.getData("osparc-moveFolder")["folderOrigin"];
          compatible = folder !== folderOrigin;
          const workspaceId = folderOrigin.getWorkspaceId();
          if (compatible) {
            if (workspaceId) {
              const workspace = osparc.store.Workspaces.getInstance().getWorkspace(workspaceId);
              if (workspace) {
                compatible = workspace.getMyAccessRights()["write"];
              }
            } else {
              compatible = true;
            }
          }
        }
        if (compatible) {
          this.getChildControl("icon").setTextColor("strong-main");
        } else {
          this.getChildControl("icon").setTextColor("danger-red");
          // do not allow
          e.preventDefault();
        }
        const dragWidget = osparc.dashboard.DragWidget.getInstance();
        dragWidget.setDropAllowed(compatible);
      });

      this.addListener("dragleave", () => {
        this.getChildControl("icon").resetTextColor();
        const dragWidget = osparc.dashboard.DragWidget.getInstance();
        dragWidget.setDropAllowed(false);
      });
      this.addListener("dragend", () => {
        this.getChildControl("icon").resetTextColor();
        const dragWidget = osparc.dashboard.DragWidget.getInstance();
        dragWidget.setDropAllowed(false);
      });

      this.addListener("drop", e => {
        if (e.supportsType("osparc-moveStudy")) {
          const studyData = e.getData("osparc-moveStudy")["studyDataOrigin"];
          const studyToFolderData = {
            studyData,
            destFolderId: this.getFolderId(),
          };
          this.fireDataEvent("studyToFolderRequested", studyToFolderData);
        } else if (e.supportsType("osparc-moveFolder")) {
          const folder = this.__getFolder();
          if (folder == null) {
            e.preventDefault();
            return;
          }

          const folderOrigin = e.getData("osparc-moveFolder")["folderOrigin"];
          const folderToFolderData = {
            folderId: folderOrigin.getFolderId(),
            destFolderId: folder.getFolderId(),
          };
          this.fireDataEvent("folderToFolderRequested", folderToFolderData);
        }
      });
    },
  },
});
