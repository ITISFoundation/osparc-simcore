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

  events: {
    "studyToFolderRequested": "qx.event.type.Data",
    "folderToFolderRequested": "qx.event.type.Data",
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
        osparc.dashboard.DragDropHelpers.moveFolder.dragStart(e, this, folderOrigin);
      });

      this.addListener("dragend", () => {
        osparc.dashboard.DragDropHelpers.dragEnd(this);
      });
    },

    __attachDropHandlers: function() {
      this.setDroppable(true);

      let draggingOver = false;
      this.addListener("dragover", e => {
        const workspaceDestId = this.getModel().getWorkspaceId();
        const folderDestId = this.getModel().getFolderId();
        if (e.supportsType("osparc-moveStudy")) {
          osparc.dashboard.DragDropHelpers.moveStudy.dragOver(e, this, workspaceDestId, folderDestId);
        } else if (e.supportsType("osparc-moveFolder")) {
          osparc.dashboard.DragDropHelpers.moveFolder.dragOver(e, this, workspaceDestId, folderDestId);
        }

        draggingOver = true;
        setTimeout(() => {
          if (draggingOver) {
            this.setOpen(true);
            draggingOver = false;
          }
        }, 1000);
      });

      this.addListener("dragleave", () => {
        osparc.dashboard.DragDropHelpers.dragLeave(this);
        draggingOver = false;
      });
      this.addListener("dragend", () => {
        osparc.dashboard.DragDropHelpers.dragLeave(this);
        draggingOver = false;
      });

      this.addListener("drop", e => {
        const workspaceDestId = this.getModel().getWorkspaceId();
        const folderDestId = this.getModel().getFolderId();
        if (e.supportsType("osparc-moveStudy")) {
          const studyToFolderData = osparc.dashboard.DragDropHelpers.moveStudy.drop(e, this, workspaceDestId, folderDestId);
          this.fireDataEvent("studyToFolderRequested", studyToFolderData);
        } else if (e.supportsType("osparc-moveFolder")) {
          const folderToFolderData = osparc.dashboard.DragDropHelpers.moveFolder.drop(e, this, workspaceDestId, folderDestId);
          this.fireDataEvent("folderToFolderRequested", folderToFolderData);
        }
        draggingOver = false;
      });
    },
  },
});
