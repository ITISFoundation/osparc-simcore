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

qx.Class.define("qxapp.component.widget.FilesTree", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let fileTreeLayout = new qx.ui.layout.Canvas();
    this._setLayout(fileTreeLayout);

    let tree = this.__tree = this._createChildControlImpl("filesTree");
    tree.getSelection().addListener("change", this.__selectionChanged, this);

    // Listen to "Enter" key
    this.addListener("keypress", function(keyEvent) {
      if (keyEvent.getKeyIdentifier() === "Enter") {
        this.__itemSelected();
      }
    }, this);
  },

  events: {
    "selectionChanged": "qx.event.type.Event",
    "itemSelected": "qx.event.type.Event"
  },

  members: {
    __tree: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filesTree":
          control = this.__createFilesTree();
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __createFilesTree: function() {
      let filesTree = new qx.ui.tree.VirtualTree(null, "label", "children").set({
        openMode: "none"
      });

      /*
      let that = this;
      let delegate = filesTree.getDelegate();
      delegate["configureItem"] = function(item) {
        item.addListener("dbltap", e => {
          that.__itemSelected(); // eslint-disable-line no-underscore-dangle
        }, that);
      };
      filesTree.setDelegate(delegate);
      */
      filesTree.setDelegate({
        configureItem: item => {
          item.addListener("dbltap", e => {
            this.__itemSelected();
          }, this);
        }
      });

      return filesTree;
    },

    populateTree: function(nodeId = null) {
      let filesTreePopulator = new qxapp.utils.FilesTreePopulator(this.__tree);
      if (nodeId) {
        filesTreePopulator.populateNodeFiles(nodeId);
      } else {
        filesTreePopulator.populateMyData();
      }
    },

    __isFile: function(item) {
      let isFile = false;
      if (item["set"+qx.lang.String.firstUp("fileId")]) {
        isFile = true;
      }
      return isFile;
    },

    __getSelectedItem: function() {
      let selection = this.__tree.getSelection().toArray();
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

    getSelection: function() {
      let selectedItem = this.__getSelectedItem();
      if (selectedItem) {
        const isFile = this.__isFile(selectedItem);
        const data = {
          selectedItem: selectedItem,
          isFile: isFile
        };
        return data;
      }
      return null;
    }
  }
});
