/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides access to the data belonging to the active user.
 * - On the left side: myData FilesTree with the FileLabelWithActions
 * - On the right side: a pie chart reflecting the data resources consumed (hidden until there is real info)
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let dataManager = new osparc.dashboard.DataBrowser();
 *   this.getRoot().add(dataManager);
 * </pre>
 */

qx.Class.define("osparc.dashboard.DataBrowser", {
  extend: osparc.dashboard.ResourceBrowserBase,

  members: {
    __filesTree: null,
    __folderViewer: null,
    __selectedFileLayout: null,

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
          break;
      }

      return control || this.base(arguments, id);
    },

    // overridden
    _initResources: function() {
      this.__buildLayout();

      this.addListener("appear", () => {
        this.getChildControl("files-tree").populateTree();
        this.getChildControl("folder-viewer").setFolder(this.getChildControl("files-tree").getModel());
      }, this);
    },

    __buildLayout: function() {
      this.set({
        marginTop: 20
      });

      // button for refetching data
      const reloadBtn = this.getChildControl("reload-button");
      reloadBtn.addListener("execute", () => {
        this.getChildControl("files-tree").resetCache();
        this.getChildControl("files-tree").populateTree();
      }, this);

      const filesTree = this.getChildControl("files-tree");
      const folderViewer = this.getChildControl("folder-viewer");

      const actionsToolbar = new qx.ui.toolbar.ToolBar();
      const fileActions = new qx.ui.toolbar.Part();
      const addFile = new qx.ui.toolbar.Part();
      actionsToolbar.add(fileActions);
      actionsToolbar.addSpacer();
      actionsToolbar.add(addFile);

      const selectedFileLayout = this.__selectedFileLayout = this.getChildControl("selected-file-layout");

      filesTree.addListener("selectionChanged", () => {
        const selectionData = filesTree.getSelectedItem();
        this.__selectionChanged(selectionData);
        if (osparc.file.FilesTree.isDir(selectionData) || (selectionData.getChildren && selectionData.getChildren().length)) {
          folderViewer.setFolder(selectionData);
        }
      }, this);

      folderViewer.addListener("selectionChanged", e => {
        const selectionData = e.getData();
        this.__selectionChanged(selectionData);
      }, this);
      folderViewer.addListener("itemSelected", e => {
        const data = e.getData();
        filesTree.openNodeAndParents(data);
        filesTree.setSelection(new qx.data.Array([data]));
      }, this);
      folderViewer.addListener("folderUp", e => {
        const currentFolder = e.getData();
        const parent = filesTree.getParent(currentFolder);
        if (parent) {
          filesTree.setSelection(new qx.data.Array([parent]));
          folderViewer.setFolder(parent);
        }
      }, this);
      folderViewer.addListener("requestDatasetFiles", e => {
        const data = e.getData();
        filesTree.requestDatasetFiles(data.locationId, data.datasetId);
      }, this);

      selectedFileLayout.addListener("fileDeleted", e => {
        const fileMetadata = e.getData();
        this.getChildControl("files-tree").populateTree(fileMetadata["locationId"]);
      }, this);
      fileActions.add(selectedFileLayout);

      this._add(actionsToolbar);
    },

    __selectionChanged: function(selectedItem) {
      this.__selectedFileLayout.itemSelected(selectedItem);
    }
  }
});
