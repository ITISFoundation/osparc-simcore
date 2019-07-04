/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * VirtualTree that uses FilesTreePopulator class to build the content.
 *
 *   Elements in the tree also accept Drag and/or Drop mechanisms which are implemented here.
 * "osparc-filePath" type is used for the Drag&Drop.
 *
 *   If a file is dropped into a folder, this class will start the copying proccess fireing
 * "fileCopied" event if successful
 *
 * Also provides two static methods for checking whether en entry in the tree is File/Directory
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let filesTree = new qxapp.file.FilesTree();
 *   this.getRoot().add(filesTree);
 * </pre>
 */

qx.Class.define("qxapp.file.FilesTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none",
      decorator: "no-border"
    });

    this.addListener("tap", this.__selectionChanged, this);

    // Listen to "Enter" key
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__itemSelected();
      }
    }, this);
  },

  properties: {
    dragMechnism: {
      check: "Boolean",
      init: false
    },

    dropMechnism: {
      check: "Boolean",
      init: false
    }
  },

  events: {
    "selectionChanged": "qx.event.type.Event",
    "itemSelected": "qx.event.type.Event",
    "fileCopied": "qx.event.type.Data",
    "modelChanged": "qx.event.type.Event"
  },

  statics: {
    isDir: function(item) {
      let isDir = false;
      if (item["get"+qx.lang.String.firstUp("path")]) {
        if (item.getPath() !== null) {
          isDir = true;
        }
      }
      return isDir;
    },

    isFile: function(item) {
      let isFile = false;
      if (item["set"+qx.lang.String.firstUp("fileId")]) {
        isFile = true;
      }
      return isFile;
    }
  },

  members: {
    populateTree: function(nodeId = null, locationId = null) {
      let filesTreePopulator = new qxapp.file.FilesTreePopulator(this);
      if (nodeId) {
        filesTreePopulator.populateNodeFiles(nodeId);
      } else if (locationId) {
        filesTreePopulator.populateMyLocation(locationId);
      } else {
        filesTreePopulator.populateMyData();
      }

      let delegate = this.getDelegate();
      delegate["configureItem"] = item => {
        item.addListener("dbltap", e => {
          this.__itemSelected();
        }, this);

        this.__addDragAndDropMechanisms(item);
      };
      this.setDelegate(delegate);
    },

    getSelectedFile: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        const isFile = qxapp.file.FilesTree.isFile(selectedItem);
        const data = {
          selectedItem: selectedItem,
          isFile: isFile
        };
        return data;
      }
      return null;
    },

    addFileEntry: function(uuid) {
      const dummyFileEntry = {
        "bucket_name": "MyFile",
        "created_at": "2019-07-03T10:01:03.471071Z",
        "display_file_path": "MyFile/testing/Hallo.csv",
        "file_id": "N:package:7b5637d5-da2e-49fc-9c54-75b5c6acf166",
        "file_name": "Hallo.csv",
        "file_size": 398,
        "file_uuid": "MyFile/testing/Hallo.csv",
        "last_modified": "2019-07-03T10:01:04.057912Z",
        "location": "datcore",
        "location_id": 1,
        "node_id": null,
        "node_name": null,
        "object_name": "testing/Hallo.csv",
        "project_id": null,
        "project_name": null,
        "raw_file_path": "MyFile/testing/Hallo.csv",
        "user_id": null,
        "user_name": null
      };

      let filesTreePopulator = new qxapp.file.FilesTreePopulator(this);
      filesTreePopulator.addFileEntryToTree(dummyFileEntry);
      const item = this.__findUuidInLeaves(dummyFileEntry["file_uuid"]);
      if (item) {
        this.openNodeAndParents(item);
      }
    },

    __getLeafList: function(item, leaves) {
      if (item.getChildren == null) { // eslint-disable-line no-eq-null
        leaves.push(item);
      } else {
        for (let i=0; i<item.getChildren().length; i++) {
          this.__getLeafList(item.getChildren().toArray()[i], leaves);
        }
      }
    },

    __findUuidInLeaves: function(uuid) {
      const parent = this.getModel();
      const list = [];
      this.__getLeafList(parent, list);
      for (let j = 0; j < list.length; j++) {
        if (uuid === list[j].getFileId()) {
          return list[j];
        }
      }
      return null;
    },

    setSelectedFile: function(fileId) {
      const item = this.__findUuidInLeaves(fileId);
      if (item) {
        this.openNodeAndParents(item);

        const selected = new qx.data.Array([item]);
        this.setSelection(selected);
      }
    },

    __getSelectedItem: function() {
      let selection = this.getSelection().toArray();
      if (selection.length > 0) {
        return selection[0];
      }
      return null;
    },

    __selectionChanged: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        this.fireEvent("selectionChanged");
      }
    },

    __itemSelected: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        this.fireEvent("itemSelected");
      }
    },

    __addDragAndDropMechanisms: function(item) {
      if (this.getDragMechnism()) {
        this.__createDragMechanism(item);
      }

      if (this.getDropMechnism()) {
        this.__createDropMechanism(item);
      }
    },

    __createDragMechanism: function(treeItem) {
      treeItem.setDraggable(true);
      treeItem.addListener("dragstart", e => {
        if (qxapp.file.FilesTree.isFile(e.getOriginalTarget())) {
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
        if (qxapp.file.FilesTree.isDir(e.getOriginalTarget())) {
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
          const store = qxapp.data.Store.getInstance();
          console.log("Copy", from.getFileId(), "to", to.getPath());
          const requestSent = store.copyFile(from.getLocation(), from.getFileId(), to.getLocation(), to.getPath());
          if (requestSent) {
            store.addListenerOnce("fileCopied", ev => {
              if (ev) {
                this.fireDataEvent("fileCopied", ev.getData());
              }
            }, this);
          }
        }
      }, this);
    }
  }
});
