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
 * Reload button
 * -------------------------------- =/- -
 * | root        |  content1  content2  |
 * |   folder1   |  content3  content4  |
 * |     folder2 |  content5  content6  |
 * --------------------------------------
 *              selected_file   Down  Del
 */

qx.Class.define("osparc.file.TreeFolderView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  statics: {
    requestPathSize: function(pathId) {
      return new Promise((resolve, reject) => {
        const fetchResult = jobId => {
          osparc.data.Resources.fetch("storagePaths", "asyncJobResult", { url: { jobId } })
            .then(result => {
              console.log(result);
              resolve(42);
            })
            .catch(reject);
        };

        const fetchStatus = jobId => {
          osparc.data.Resources.fetch("storagePaths", "asyncJobStatus", { url: { jobId } })
            .then(status => {
              if (status["done"]) {
                fetchResult(jobId);
              } else {
                setTimeout(() => fetchStatus(jobId), 1000);
              }
            })
            .catch(reject);
        };

        osparc.data.Resources.fetch("storagePaths", "requestSize", { url: { pathId } })
          .then(resp => {
            const jobId = resp["job_id"];
            if (jobId) {
              fetchStatus(jobId);
            }
          })
          .catch(reject);
      });
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._add(control);
          break;
        case "reload-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            font: "text-14",
            icon: "@FontAwesome5Solid/sync-alt/14",
            allowGrowX: false
          });
          this.getChildControl("header-layout").add(control);
          this.getChildControl("header-layout").add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          break;
        case "total-size-label":
          control = new qx.ui.basic.Atom().set({
            label: this.tr("Calculating Size"),
            font: "text-14",
            icon: "@FontAwesome5Solid/spinner/14",
            allowGrowX: false
          });
          this.getChildControl("header-layout").add(control);
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
        case "folder-tree": {
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
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("reload-button");
      const folderTree = this.getChildControl("folder-tree");
      const folderViewer = this.getChildControl("folder-viewer");

      folderTree.addListener("selectionChanged", () => {
        const selectedModel = folderTree.getSelectedItem();
        if (selectedModel) {
          if (selectedModel.getPath() && !selectedModel.getLoaded()) {
            folderTree.requestPathItems(selectedModel.getLocation(), selectedModel.getPath())
              .then(pathModel => {
                if (osparc.file.FilesTree.isDir(pathModel)) {
                  folderViewer.setFolder(pathModel);
                }
              });
          } else if (osparc.file.FilesTree.isDir(selectedModel)) {
            folderViewer.setFolder(selectedModel);
          }
        }
      }, this);

      folderViewer.addListener("openItemSelected", e => {
        const selectedModel = e.getData();
        if (selectedModel) {
          if (selectedModel.getPath() && !selectedModel.getLoaded()) {
            folderTree.requestPathItems(selectedModel.getLocation(), selectedModel.getPath())
              .then(pathModel => {
                folderTree.openNodeAndParents(pathModel);
                folderTree.setSelection(new qx.data.Array([pathModel]));
                if (osparc.file.FilesTree.isDir(pathModel)) {
                  folderViewer.setFolder(pathModel);
                }
              });
          } else if (osparc.file.FilesTree.isDir(selectedModel)) {
            folderViewer.setFolder(selectedModel);
          }
        }
      }, this);

      folderViewer.addListener("folderUp", e => {
        const currentFolder = e.getData();
        const parent = folderTree.getParent(currentFolder);
        if (parent) {
          folderTree.setSelection(new qx.data.Array([parent]));
          if (osparc.file.FilesTree.isDir(parent)) {
            folderViewer.setFolder(parent);
          }
        }
      }, this);
    },

    openPath: function(path) {
      const foldersTree = this.getChildControl("folder-tree");
      const folderViewer = this.getChildControl("folder-viewer");
      let found = false;
      while (!found && path.length) {
        found = foldersTree.findItemId(path.join("/"));
        // look for next parent
        path.pop();
      }
      if (found) {
        foldersTree.openNodeAndParents(found);
        foldersTree.setSelection(new qx.data.Array([found]));
        foldersTree.fireEvent("selectionChanged");
      } else {
        folderViewer.resetFolder();
      }
    },

    requestSize: function(pathId) {
      const totalSize = this.getChildControl("total-size-label");
      totalSize.getChildControl("icon").getContentElement().addClass("rotate");
      this.self().requestPathSize(pathId)
        .then(size => {
          totalSize.set({
            icon: null,
            label: osparc.utils.Utils.bytesToSize(size),
          });
        })
        .catch(err => {
          console.error(err);
          totalSize.hide();
        });
    }
  }
});
