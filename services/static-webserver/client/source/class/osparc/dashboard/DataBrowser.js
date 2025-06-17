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
          control = new osparc.file.TreeFolderView().set({
            paddingBottom: 15,
          });
          this._addToLayout(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    // overridden
    initResources: function() {
      if (this._resourcesInitialized) {
        return;
      }
      this._resourcesInitialized = true;

      this._hideLoadingPage();
      this.__buildLayout();

      this.addListener("appear", () => {
        const treeFolderView = this.getChildControl("tree-folder-view");
        treeFolderView.getChildControl("folder-tree").populateLocations();
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

      const selectedFileLayout = treeFolderView.getChildControl("folder-viewer").getChildControl("selected-file-layout");
      selectedFileLayout.addListener("pathsDeleted", e => treeFolderView.pathsDeleted(e.getData()), this);
    },

    __reloadTree: function() {
      const treeFolderView = this.getChildControl("tree-folder-view");

      const foldersTree = treeFolderView.getChildControl("folder-tree");
      foldersTree.resetCache();
      foldersTree.populateLocations();

      const folderViewer = treeFolderView.getChildControl("folder-viewer");
      folderViewer.resetFolder();
    },
  }
});
