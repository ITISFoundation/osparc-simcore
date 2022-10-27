/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that contains FilesTree showing:
 * - data generated by the node
 * and a FileLabelWithActions for letting the user download and/or remove files.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let dataManager = new osparc.component.widget.NodeDataManager(nodeId);
 *   this.getRoot().add(dataManager);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeDataManager", {
  extend: qx.ui.core.Widget,

  /**
    * @param nodeId {String} NodeId
    */
  construct: function(nodeId) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    if (nodeId) {
      this.set({
        nodeId: nodeId
      });
    }

    this.__buildLayout();
    this.__reloadTree();
  },

  properties: {
    nodeId: {
      check: "String",
      init: null,
      nullable: false
    }
  },

  members: {
    __filesTree: null,
    __selectedFileLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "files-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._add(control, {
            flex: 1
          });
          break;
        case "reload-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            icon: "@FontAwesome5Solid/sync-alt/16",
            allowGrowX: false
          });
          break;
        case "tree-folder-layout":
          control = new qx.ui.splitpane.Pane("horizontal");
          control.getChildControl("splitter").set({
            width: 2,
            backgroundColor: "scrollbar-passive"
          });
          break;
        case "files-tree":
          control = new osparc.file.FilesTree().set({
            minWidth: 150,
            width: 200,
            backgroundColor: "transparent"
          });
          break;
        case "folder-viewer":
          control = new osparc.file.FolderViewer();
          break;
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
      const treesLayout = this.getChildControl("files-layout");

      const treeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      const reloadBtn = this.getChildControl("reload-button");
      reloadBtn.addListener("execute", () => this.__reloadTree(), this);
      treeLayout.add(reloadBtn);

      const filesTree = this.__filesTree = this.getChildControl("files-tree").set({
        showLeafs: false
      });
      const folderViewer = this.getChildControl("folder-viewer");
      const treeFolderLayout = this.getChildControl("tree-folder-layout");
      treeFolderLayout.add(filesTree, 0);
      treeFolderLayout.add(folderViewer, 1);

      filesTree.addListener("selectionChanged", () => {
        const selectionData = filesTree.getSelectedItem();
        this.__selectionChanged(selectionData);
        if (selectionData) {
          if (osparc.file.FilesTree.isDir(selectionData) || (selectionData.getChildren && selectionData.getChildren().length)) {
            folderViewer.setFolder(selectionData);
          }
        }
      }, this);
      folderViewer.addListener("selectionChanged", e => {
        const selectionData = e.getData();
        this.__selectionChanged(selectionData);
      }, this);
      folderViewer.addListener("folderUp", e => {
        const currentFolder = e.getData();
        const parent = filesTree.getParent(currentFolder);
        if (parent) {
          filesTree.setSelection(new qx.data.Array([parent]));
          folderViewer.setFolder(parent);
        }
      }, this);

      treeLayout.add(treeFolderLayout, {
        flex: 1
      });

      treesLayout.add(treeLayout, {
        flex: 1
      });

      const selectedFileLayout = this.__selectedFileLayout = this.getChildControl("selected-file-layout");
      selectedFileLayout.addListener("fileDeleted", () => this.__reloadTree(), this);
    },

    __reloadTree: function() {
      if (this.__filesTree) {
        this.__filesTree.populateNodeTree(this.getNodeId());
      }
    },

    __selectionChanged: function(selectionData) {
      if (selectionData) {
        this.__selectedFileLayout.setItemSelected(selectionData);
      }
    }
  }
});
