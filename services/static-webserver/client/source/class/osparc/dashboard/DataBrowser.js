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

  construct: function() {
    this._resourceType = "data";
    this.base(arguments);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tree-folder-view":
          control = new osparc.file.TreeFolderView();
          this._addToLayout(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    // overridden
    initResources: function() {
      this._hideLoadingPage();
      this.__buildLayout();

      this.addListener("appear", () => {
        const treeFolderView = this.getChildControl("tree-folder-view");
        treeFolderView.getChildControl("folder-tree").populateTree();
        treeFolderView.getChildControl("folder-viewer").setFolder(treeFolderView.getChildControl("folder-tree").getModel());
      }, this);
    },

    __buildLayout: function() {
      this.set({
        marginTop: 20
      });

      const treeFolderView = this.getChildControl("tree-folder-view");

      const reloadButton = treeFolderView.getChildControl("reload-button");
      reloadButton.addListener("execute", () => this.__reloadTree(), this);

      const selectedFileLayout = treeFolderView.getChildControl("selected-file-layout");
      selectedFileLayout.addListener("fileDeleted", e => this.__fileDeleted(e.getData()), this);
    },

    __reloadTree: function() {
      const treeFolderView = this.getChildControl("tree-folder-view");

      const foldersTree = treeFolderView.getChildControl("folder-tree");
      foldersTree.resetCache();
      foldersTree.populateTree();

      const folderViewer = treeFolderView.getChildControl("folder-viewer");
      folderViewer.resetFolder();
    },

    __fileDeleted: function(fileMetadata) {
      // After deleting a file, try to keep the user in the same folder.
      // If the folder doesn't longer exist, open the closest available parent

      const path = fileMetadata["fileUuid"].split("/");

      const treeFolderView = this.getChildControl("tree-folder-view");
      const foldersTree = treeFolderView.getChildControl("folder-tree");
      const folderViewer = treeFolderView.getChildControl("folder-viewer");

      const openSameFolder = () => {
        // drop last, which is the file
        path.pop();
        treeFolderView.openPath(path);
      };

      folderViewer.resetFolder();
      const locationId = fileMetadata["locationId"];
      const datasetId = path[0];
      foldersTree.resetCache();
      foldersTree.populateTree()
        .then(datasetPromises => {
          Promise.all(datasetPromises)
            .then(() => foldersTree.requestDatasetFiles(locationId, datasetId))
            .then(() => openSameFolder());
        })
        .catch(err => console.error(err));
    }
  }
});
