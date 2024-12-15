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
        const folderOrigin = this.__getFolder();
        // only folders can be dragged
        if (folderOrigin == null) {
          e.preventDefault();
          return;
        }
        osparc.dashboard.DragDropHelpers.moveFolder.dragStart(e, folderOrigin, this);
      });

      this.addListener("dragend", () => {
        osparc.dashboard.DragDropHelpers.dragEnd(this);
      });
    },

    __attachDropHandlers: function() {
      this.setDroppable(true);

      this.addListener("dragover", e => {
        if (e.supportsType("osparc-moveStudy")) {
          let compatible = false;
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
          if (compatible) {
            this.getChildControl("icon").setTextColor("strong-main");
          } else {
            this.getChildControl("icon").setTextColor("danger-red");
            // do not allow
            e.preventDefault();
          }
          const dragWidget = osparc.dashboard.DragWidget.getInstance();
          dragWidget.setDropAllowed(compatible);
        } else if (e.supportsType("osparc-moveFolder")) {
          const folderDest = this.__getFolder();
          if (folderDest == null) {
            e.preventDefault();
            return;
          }
          osparc.dashboard.DragDropHelpers.moveFolder.dragOver(e, folderDest, this);
        }
      });

      this.addListener("dragleave", () => {
        osparc.dashboard.DragDropHelpers.dragLeave(this);
      });
      this.addListener("dragend", () => {
        osparc.dashboard.DragDropHelpers.dragLeave(this);
      });

      this.addListener("drop", e => {
        if (e.supportsType("osparc-moveStudy")) {
          const folderDest = this.__getFolder();
          if (folderDest == null) {
            e.preventDefault();
            return;
          }
          const studyData = e.getData("osparc-moveStudy")["studyDataOrigin"];
          const studyToFolderData = {
            studyData,
            destFolderId: folderDest.getFolderId(),
          };
          this.fireDataEvent("studyToFolderRequested", studyToFolderData);
        } else if (e.supportsType("osparc-moveFolder")) {
          const folderDest = this.__getFolder();
          if (folderDest == null) {
            e.preventDefault();
            return;
          }
          const folderToFolderData = osparc.dashboard.DragDropHelpers.moveFolder.drop(e, folderDest);
          this.fireDataEvent("folderToFolderRequested", folderToFolderData);
        }
      });
    },
  },
});
