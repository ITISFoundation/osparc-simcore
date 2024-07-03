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
 * --------------------------------------
 * | root        |  content1  content2  |
 * |   folder1   |                      |
 * |     folder2 |                      |
 * --------------------------------------
 */

qx.Class.define("osparc.file.TreeFolderView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "reload-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            font: "text-14",
            icon: "@FontAwesome5Solid/sync-alt/14",
            allowGrowX: false
          });
          this._add(control);
          break;
        case "tree-folder-layout":
          control = new qx.ui.splitpane.Pane("horizontal");
          control.getChildControl("splitter").set({
            width: 2,
            backgroundColor: "scrollbar-passive"
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "files-tree": {
          const treeFolderLayout = this.getChildControl("tree-folder-layout");
          control = new osparc.file.FilesTree().set({
            showLeafs: false,
            minWidth: 150,
            width: 250
          });
          treeFolderLayout.add(control, 0);
          break;
        }
        case "folder-viewer": {
          const treeFolderLayout = this.getChildControl("tree-folder-layout");
          control = new osparc.file.FolderViewer();
          treeFolderLayout.add(control, 1);
          break;
        }
        case "selected-file-layout":
          control = new osparc.file.FileLabelWithActions().set({
            alignY: "middle"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("reload-button");
      const foldersTree = this.getChildControl("files-tree");
      const folderViewer = this.getChildControl("folder-viewer");
      const selectedFileLayout = this.getChildControl("selected-file-layout");

      // Connect elements
      foldersTree.addListener("selectionChanged", () => {
        const selectionData = foldersTree.getSelectedItem();
        if (selectionData) {
          selectedFileLayout.setItemSelected(selectionData);
          if (osparc.file.FilesTree.isDir(selectionData) || (selectionData.getChildren && selectionData.getChildren().length)) {
            folderViewer.setFolder(selectionData);
          }
        }
      }, this);

      folderViewer.addListener("selectionChanged", e => {
        const selectionData = e.getData();
        if (selectionData) {
          selectedFileLayout.setItemSelected(selectionData);
        }
      }, this);

      folderViewer.addListener("itemSelected", e => {
        const data = e.getData();
        foldersTree.openNodeAndParents(data);
        foldersTree.setSelection(new qx.data.Array([data]));
      }, this);

      folderViewer.addListener("folderUp", e => {
        const currentFolder = e.getData();
        const parent = foldersTree.getParent(currentFolder);
        if (parent) {
          foldersTree.setSelection(new qx.data.Array([parent]));
          folderViewer.setFolder(parent);
        }
      }, this);

      folderViewer.addListener("requestDatasetFiles", e => {
        const data = e.getData();
        foldersTree.requestDatasetFiles(data.locationId, data.datasetId);
      }, this);

      selectedFileLayout.addListener("fileDeleted", e => {
        const fileMetadata = e.getData();
        foldersTree.populateTree(fileMetadata["locationId"]);
      }, this);
    }
  }
});
