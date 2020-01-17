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
    * @param showUsersTree {Boolean} Show the user's tree on the right side. True by default
    */
  construct: function(node, showUsersTree = true) {
    this.base(arguments);

    this.set({
      node: node
    });

    osparc.utils.Utils.setIdToWidget(this, "nodeDataManager");

    const nodeDataManagerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(nodeDataManagerLayout);

    const treesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
    this._add(treesLayout, {
      flex: 1
    });

    const nodeTreeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
    const nodeReloadBtn = this._createChildControlImpl("reloadButton");
    nodeReloadBtn.addListener("execute", function() {
      this.__reloadNodeTree();
    }, this);
    nodeTreeLayout.add(nodeReloadBtn);
    const nodeFilesTree = this.__nodeFilesTree = this._createChildControlImpl("nodeTree");
    osparc.utils.Utils.setIdToWidget(nodeFilesTree, "nodeDataManagerNodeFilesTree");
    nodeFilesTree.setDragMechnism(true);
    nodeFilesTree.addListener("selectionChanged", () => {
      this.__selectionChanged("node");
    }, this);
    nodeTreeLayout.add(nodeFilesTree, {
      flex: 1
    });
    treesLayout.add(nodeTreeLayout, {
      flex: 1
    });

    if (showUsersTree) {
      const userTreeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const userReloadBtn = this._createChildControlImpl("reloadButton");
      userReloadBtn.addListener("execute", function() {
        this.__userFilesTree.resetCache();
        this.__reloadUserTree();
      }, this);
      userTreeLayout.add(userReloadBtn);
      const userFilesTree = this.__userFilesTree = this._createChildControlImpl("userTree");
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
    }

    const selectedFileLayout = this.__selectedFileLayout = this._createChildControlImpl("selectedFileLayout");
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
      check: "osparc.data.model.Node"
    }
  },

  members: {
    __nodeFilesTree: null,
    __userFilesTree: null,
    __selectedFileLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "reloadButton":
          control = new qx.ui.form.Button().set({
            label: this.tr("Reload"),
            icon: "@FontAwesome5Solid/sync-alt/16",
            allowGrowX: false
          });
          break;
        case "nodeTree":
        case "userTree":
          control = new osparc.file.FilesTree();
          break;
        case "selectedFileLayout":
          control = new osparc.file.FileLabelWithActions().set({
            alignY: "middle"
          });
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    getWindow: function() {
      const win = new qx.ui.window.Window(this.getNode().getLabel()).set({
        appearance: "service-window",
        layout: new qx.ui.layout.Grow(),
        autoDestroy: true,
        contentPadding: 0,
        height: 600,
        modal: true,
        showMinimize: false,
        width: 900
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
      win.add(this);
      win.center();
      return win;
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
        selectionData = this.__userFilesTree.getSelectedFile();
      } else {
        if (this.__userFilesTree) {
          this.__userFilesTree.resetSelection();
        }
        selectionData = this.__nodeFilesTree.getSelectedFile();
      }
      if (selectionData) {
        this.__selectedFileLayout.itemSelected(selectionData["selectedItem"], selectionData["isFile"]);
      }
    }
  }
});
