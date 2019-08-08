/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that contains 2 FilesTree showing:
 * - data generated by the node
 * - data owned by the user
 * and a FileLabelWithActions for letting the user download and/or remove files.
 *
 *   It also provideds Drag&Drop mechanism for copying data from the node into user's data.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeDataManager = new qxapp.component.widget.NodeDataManager(node);
 *   this.getRoot().add(nodeDataManager);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NodeDataManager", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
  */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    let nodeDataManagerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeDataManagerLayout);

    let treesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
    this._add(treesLayout, {
      flex: 1
    });

    let nodeFilesTree = this.__nodeFilesTree = this._createChildControlImpl("nodeTree");
    nodeFilesTree.setDragMechnism(true);
    nodeFilesTree.addListener("selectionChanged", () => {
      this.__selectionChanged("node");
    }, this);
    treesLayout.add(nodeFilesTree, {
      flex: 1
    });

    let userFilesTree = this.__userFilesTree = this._createChildControlImpl("userTree");
    userFilesTree.setDropMechnism(true);
    userFilesTree.addListener("selectionChanged", () => {
      this.__selectionChanged("user");
    }, this);
    userFilesTree.addListener("fileCopied", e => {
      const fileMetadata = e.getData();
      if (fileMetadata) {
        this.__userFilesTree.addFileEntry(fileMetadata);
      }
    }, this);
    treesLayout.add(userFilesTree, {
      flex: 1
    });

    let selectedFileLayout = this.__selectedFileLayout = this._createChildControlImpl("selectedFileLayout");
    selectedFileLayout.addListener("fileDeleted", e => {
      const fileMetadata = e.getData();
      this.__reloadNodeTree();
      this.__reloadUserTree(fileMetadata["locationId"]);
    }, this);

    this.__reloadNodeTree();
    this.__reloadUserTree();
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node"
    }
  },

  members: {
    __nodeFilesTree: null,
    __userFilesTree: null,
    __selectedFileLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "nodeTree":
        case "userTree":
          control = new qxapp.file.FilesTree();
          break;
        case "selectedFileLayout":
          control = new qxapp.file.FileLabelWithActions().set({
            alignY: "middle"
          });
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __reloadNodeTree: function() {
      this.__nodeFilesTree.populateTree(this.getNode().getNodeId());
    },

    __reloadUserTree: function(locationId = null) {
      this.__userFilesTree.populateTree(null, locationId);
    },

    __selectionChanged: function(selectedTree) {
      let selectionData = null;
      if (selectedTree === "user") {
        this.__nodeFilesTree.resetSelection();
        selectionData = this.__userFilesTree.getSelectedFile();
      } else {
        this.__userFilesTree.resetSelection();
        selectionData = this.__nodeFilesTree.getSelectedFile();
      }
      if (selectionData) {
        this.__selectedFileLayout.itemSelected(selectionData["selectedItem"], selectionData["isFile"]);
      }
    }
  }
});
