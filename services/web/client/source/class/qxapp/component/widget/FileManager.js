/* global document */
/* global XMLHttpRequest */
/* global Blob */
/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.component.widget.FileManager", {
  extend: qx.ui.core.Widget,

  construct: function(nodeModel) {
    this.base(arguments);

    this.set({
      nodeModel: nodeModel
    });

    let fileManagerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(fileManagerLayout);

    let treesLayout = this._createChildControlImpl("treesLayout");

    let nodeTree = this.__nodeTree = this._createChildControlImpl("nodeTree");
    treesLayout.add(nodeTree, {
      flex: 1
    });
    nodeTree.getSelection().addListener("change", this.__nodeItemSelected, this);

    let userTree = this.__userTree = this._createChildControlImpl("userTree");
    treesLayout.add(userTree, {
      flex: 1
    });
    userTree.getSelection().addListener("change", this.__userItemSelected, this);

    let selectedFileLayout = this._createChildControlImpl("selectedFileLayout");
    {
      let selectedLabel = this.__selectedLabel = new qx.ui.basic.Label().set({
        decorator: "main",
        backgroundColor: "white",
        allowGrowX: true,
        height: 24
      });

      let downloadBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/cloud-download-alt/24"
      });
      downloadBtn.addListener("execute", e => {
        this.__retrieveURLAndDownload();
      }, this);

      let deleteBtn = new qx.ui.form.Button().set({
        icon: "@FontAwesome5Solid/trash-alt/24"
      });
      deleteBtn.addListener("execute", e => {
        this.__deleteFile();
      }, this);

      selectedFileLayout.add(selectedLabel, {
        flex: 1
      });
      selectedFileLayout.add(downloadBtn);
      selectedFileLayout.add(deleteBtn);
    }

    let closeBtn = this.__closeBtn = this._createChildControlImpl("closeButton");
    closeBtn.setEnabled(false);
    closeBtn.addListener("execute", function() {
      console.log("close");
    }, this);

    this.__reloadNodeTree();
    this.__reloadUserTree();
  },

  properties: {
    nodeModel: {
      check: "qxapp.data.model.NodeModel"
    }
  },

  members: {
    __nodeTree: null,
    __userTree: null,
    __currentUserId: "ODEI-UUID",
    __selectedLabel: null,
    __selection: null,
    __closeBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "treesLayout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this._add(control, {
            flex: 1
          });
          break;
        case "nodeTree":
        case "userTree":
          control = new qx.ui.tree.VirtualTree(null, "label", "children").set({
            openMode: "none"
          });
          break;
        case "selectedFileLayout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5)).set({
            alignY: "middle"
          });
          this._add(control);
          break;
        case "closeButton":
          control = new qx.ui.form.Button(this.tr("Close"));
          this._add(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    __reloadNodeTree: function() {
      let filesTreePopulator = new qxapp.utils.FilesTreePopulator(this.__nodeTree);
      filesTreePopulator.populateNodeFiles(this.getNodeModel().getNodeId());

      let that = this;
      let delegate = this.__nodeTree.getDelegate();
      delegate["configureItem"] = function(item) {
        that.__createDragMechanism(item); // eslint-disable-line no-underscore-dangle
      };
      this.__nodeTree.setDelegate(delegate);
    },

    __reloadUserTree: function() {
      let filesTreePopulator = new qxapp.utils.FilesTreePopulator(this.__userTree);
      filesTreePopulator.populateMyDocuments();

      let that = this;
      let delegate = this.__userTree.getDelegate();
      delegate["configureItem"] = function(item) {
        that.__createDropMechanism(item); // eslint-disable-line no-underscore-dangle
      };
      this.__userTree.setDelegate(delegate);
    },

    __isFile: function(item) {
      let isFile = false;
      if (item["get"+qx.lang.String.firstUp("fileId")]) {
        if (item.getFileId() !== null) {
          isFile = true;
        }
      }
      return isFile;
    },

    __isDir: function(item) {
      let isDir = false;
      if (item["get"+qx.lang.String.firstUp("path")]) {
        if (item.getPath() !== null) {
          isDir = true;
        }
      }
      return isDir;
    },

    __createDragMechanism: function(treeItem) {
      treeItem.setDraggable(true);
      treeItem.addListener("dragstart", e => {
        if (this.__isFile(e.getOriginalTarget())) {
          // Register supported actions
          e.addAction("copy");
          // Register supported types
          e.addType("osparc-filePath");
        } else {
          e.preventDefault();
        }
      }, this);
    },

    __createDropMechanism: function(treeItem) {
      treeItem.setDroppable(true);
      treeItem.addListener("dragover", e => {
        let compatible = false;
        if (this.__isDir(e.getOriginalTarget())) {
          if (e.supportsType("osparc-filePath")) {
            compatible = true;
          }
        }
        if (!compatible) {
          e.preventDefault();
        }
      }, this);

      treeItem.addListener("drop", e => {
        if (e.supportsType("osparc-filePath")) {
          const from = e.getRelatedTarget();
          const to = e.getCurrentTarget();
          let store = qxapp.data.Store.getInstance();
          console.log("Copy", from.getFileId(), "to", to.getPath());
          store.copyFile(from.getLocation(), from.getFileId(), to.getLocation(), to.getPath());
          store.addListenerOnce("FileCopied", ev => {
            this.__reloadUserTree();
          }, this);
        }
      }, this);
    },

    __nodeItemSelected: function() {
      let selectedItem = this.__nodeTree.getSelection();
      if (selectedItem.length < 1) {
        return;
      }
      this.__userTree.resetSelection();
      selectedItem = selectedItem.toArray();
      this.__itemSelected(selectedItem[0]);
    },

    __userItemSelected: function() {
      let selectedItem = this.__userTree.getSelection();
      if (selectedItem.length < 1) {
        return;
      }
      this.__nodeTree.resetSelection();
      selectedItem = selectedItem.toArray();
      this.__itemSelected(selectedItem[0]);
    },

    __itemSelected: function(selectedItem) {
      if (this.__isFile(selectedItem)) {
        this.__selection = selectedItem;
        this.__selectedLabel.setValue(selectedItem.getFileId());
      } else {
        this.__selection = null;
        this.__selectedLabel.setValue("");
      }
    },

    __getItemSelected: function() {
      let selectedItem = this.__selection;
      if (selectedItem && this.__isFile(selectedItem)) {
        return selectedItem;
      }
      return null;
    },

    // Request to the server an download
    __retrieveURLAndDownload: function() {
      let selection = this.__getItemSelected();
      if (selection) {
        const fileId = selection.getFileId();
        let fileName = fileId.split("/");
        fileName = fileName[fileName.length-1];
        let store = qxapp.data.Store.getInstance();
        store.addListenerOnce("PresginedLink", e => {
          const presginedLinkData = e.getData();
          console.log(presginedLinkData.presginedLink);
          if (presginedLinkData.presginedLink) {
            this.__downloadFile(presginedLinkData.presginedLink.link, fileName);
          }
        }, this);
        const download = true;
        const locationId = selection.getLocation();
        store.getPresginedLink(download, locationId, fileId);
      }
    },

    __downloadFile: function(url, fileName) {
      let xhr = new XMLHttpRequest();
      xhr.open("GET", url, true);
      xhr.responseType = "blob";
      xhr.onload = () => {
        console.log("onload", xhr);
        if (xhr.status == 200) {
          let blob = new Blob([xhr.response]);
          let urlBlob = window.URL.createObjectURL(blob);
          let downloadAnchorNode = document.createElement("a");
          downloadAnchorNode.setAttribute("href", urlBlob);
          downloadAnchorNode.setAttribute("download", fileName);
          downloadAnchorNode.click();
          downloadAnchorNode.remove();
        }
      };
      xhr.send();
    },

    __deleteFile: function() {
      let selection = this.__getItemSelected();
      if (selection) {
        console.log("Delete ", selection);
        const fileId = selection.getFileId();
        const locationId = selection.getLocation();
        let store = qxapp.data.Store.getInstance();
        store.addListenerOnce("DeleteFile", e => {
          this.__reloadNodeTree();
          this.__reloadUserTree();
        }, this);
        store.deleteFile(locationId, fileId);
      }
    }
  }
});
