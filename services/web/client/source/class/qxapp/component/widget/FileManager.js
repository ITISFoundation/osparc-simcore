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

/* global document */
/* global XMLHttpRequest */
/* global Blob */
/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.component.widget.FileManager", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this.set({
      node: node
    });

    let fileManagerLayout = new qx.ui.layout.VBox(10);
    this._setLayout(fileManagerLayout);

    let treesLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
    this._add(treesLayout, {
      flex: 1
    });

    let nodeTree = this.__nodeTree = this._createChildControlImpl("nodeTree");
    nodeTree.setDragMechnism(true);
    nodeTree.addListener("selectionChanged", () => {
      this.__selectionChanged("node");
    }, this);
    treesLayout.add(nodeTree, {
      flex: 1
    });

    let userTree = this.__userTree = this._createChildControlImpl("userTree");
    userTree.setDropMechnism(true);
    userTree.addListener("selectionChanged", () => {
      this.__selectionChanged("user");
    }, this);
    userTree.addListener("fileCopied", e => {
      this.__reloadUserTree();
    }, this);
    treesLayout.add(userTree, {
      flex: 1
    });

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
    node: {
      check: "qxapp.data.model.Node"
    }
  },

  members: {
    __nodeTree: null,
    __userTree: null,
    __selectedLabel: null,
    __selection: null,
    __closeBtn: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "nodeTree":
        case "userTree":
          control = new qxapp.component.widget.FilesTree();
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
      this.__nodeTree.populateTree(this.getNode().getNodeId());
    },

    __reloadUserTree: function() {
      this.__userTree.populateTree();
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

    __selectionChanged: function(selectedTree) {
      let selectionData = null;
      if (selectedTree === "user") {
        this.__nodeTree.resetSelection();
        selectionData = this.__userTree.getSelectedFile();
      } else {
        this.__userTree.resetSelection();
        selectionData = this.__nodeTree.getSelectedFile();
      }
      if (selectionData) {
        this.__itemSelected(selectionData["selectedItem"], selectionData["isFile"]);
      }
    },

    __itemSelected: function(selectedItem, isFile) {
      if (isFile) {
        this.__selection = selectedItem;
        this.__selectedLabel.setValue(selectedItem.getFileId());
      } else {
        this.__selection = null;
        this.__selectedLabel.setValue("");
      }
    },

    __getItemSelected: function() {
      let selectedItem = this.__selection;
      if (selectedItem && qxapp.component.widget.FilesTree.isFile(selectedItem)) {
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
        store.addListenerOnce("presginedLink", e => {
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
        store.addListenerOnce("deleteFile", e => {
          this.__reloadNodeTree();
          this.__reloadUserTree();
        }, this);
        store.deleteFile(locationId, fileId);
      }
    }
  }
});
