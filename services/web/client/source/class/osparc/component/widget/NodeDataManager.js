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
 *   let nodeDataManager = new osparc.component.widget.NodeDataManager(node);
 *   this.getRoot().add(nodeDataManager);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeDataManager", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    osparc.utils.Utils.setIdToWidget(this, "nodeDataManager");

    this.__buildLayout();
    this.__reloadNodeTree();
    this.__reloadUserTree();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    showMyData: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeShowMyData"
    }
  },

  members: {
    __nodeFilesTree: null,
    __userFilesTree: null,
    __selectedFileLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "show-my-data-checkbox":
          control = new qx.ui.form.CheckBox().set({
            label: this.tr("Show My Data"),
            alignX: "right",
            value: this.getShowMyData()
          });
          this._add(control);
          break;
        case "reload-button":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            icon: "@FontAwesome5Solid/sync-alt/16",
            allowGrowX: false
          });
          break;
        case "node-tree-folder-layout":
        case "user-tree-folder-layout":
          control = new qx.ui.splitpane.Pane("horizontal");
          break;
        case "node-tree":
        case "user-tree":
          control = new osparc.file.FilesTree();
          break;
        case "node-folder-viewer":
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
      const nodeDataManagerLayout = new qx.ui.layout.VBox(10);
      this._setLayout(nodeDataManagerLayout);

      const showMyData = this.getChildControl("show-my-data-checkbox");
      showMyData.bind("value", this, "showMyData");

      const treesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      this._add(treesLayout, {
        flex: 1
      });


      const nodeTreeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());

      const nodeReloadBtn = this.getChildControl("reload-button");
      nodeReloadBtn.addListener("execute", function() {
        this.__reloadNodeTree();
      }, this);
      nodeTreeLayout.add(nodeReloadBtn);

      const nodeTreeFolderLayout = this.getChildControl("node-tree-folder-layout");
      const nodeFilesTree = this.__nodeFilesTree = this.getChildControl("node-tree");
      nodeFilesTree.setDragMechanism(true);
      nodeFilesTree.setWidth(200);
      nodeTreeFolderLayout.add(nodeFilesTree, 0);
      const nodeFolder = this.getChildControl("node-folder-viewer");
      nodeTreeFolderLayout.add(nodeFolder, 1);

      nodeFilesTree.addListener("selectionChanged", () => {
        this.__selectionChanged("node");
        const selectionData = nodeFilesTree.getSelectedItem();
        if (osparc.file.FilesTree.isDir(selectionData) || (selectionData.getChildren && selectionData.getChildren().length)) {
          nodeFolder.setFolder(selectionData);
        }
      }, this);

      nodeTreeLayout.add(nodeTreeFolderLayout, {
        flex: 1
      });

      treesLayout.add(nodeTreeLayout, {
        flex: 1
      });


      const userTreeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      this.bind("showMyData", userTreeLayout, "visibility", {
        converter: showMyDataValue => showMyDataValue ? "visible" : "excluded"
      });

      const userReloadBtn = this.getChildControl("reload-button");
      userReloadBtn.addListener("execute", function() {
        this.__userFilesTree.resetCache();
        this.__reloadUserTree();
      }, this);
      userTreeLayout.add(userReloadBtn);

      const userFilesTree = this.__userFilesTree = this.getChildControl("user-tree");
      osparc.utils.Utils.setIdToWidget(nodeFilesTree, "nodeDataManagerUserFilesTree");
      userFilesTree.setDropMechnism(true);
      userFilesTree.addListener("selectionChanged", () => {
        this.__selectionChanged("user");
      }, this);
      userFilesTree.addListener("fileCopied", e => {
        const fileMetadata = e.getData();
        if (fileMetadata) {
          console.log("file copied", fileMetadata);
        }
      }, this);
      userTreeLayout.add(userFilesTree, {
        flex: 1
      });

      treesLayout.add(userTreeLayout, {
        flex: 1
      });


      const selectedFileLayout = this.__selectedFileLayout = this.getChildControl("selected-file-layout");
      selectedFileLayout.addListener("fileDeleted", e => {
        const fileMetadata = e.getData();
        this.__reloadNodeTree();
        this.__reloadUserTree(fileMetadata["locationId"]);
      }, this);
    },

    __reloadNodeTree: function() {
      if (this.__nodeFilesTree) {
        this.__nodeFilesTree.populateNodeTree(this.getNode().getNodeId());
      }
    },

    __reloadUserTree: function(locationId = null) {
      if (this.__userFilesTree) {
        this.__userFilesTree.populateTree(locationId);
      }
    },

    __selectionChanged: function(selectedTree) {
      let selectionData = null;
      if (selectedTree === "user") {
        this.__nodeFilesTree.resetSelection();
        selectionData = this.__userFilesTree.getSelectedItem();
      } else {
        if (this.__userFilesTree) {
          this.__userFilesTree.resetSelection();
        }
        selectionData = this.__nodeFilesTree.getSelectedItem();
      }
      if (selectionData) {
        this.__selectedFileLayout.itemSelected(selectionData);
      }
    }
  }
});
