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
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none"
    });

    this.getSelection().addListener("change", this.__selectionChanged, this);

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

    populateTree: function(nodeId = null) {
      let filesTreePopulator = new qxapp.utils.FilesTreePopulator(this);
      if (nodeId) {
        filesTreePopulator.populateNodeFiles(nodeId);
      } else {
        filesTreePopulator.populateMyData();
      }

      let delegate = this.getDelegate();
      delegate["configureItem"] = item => {
        item.addListener("dbltap", e => {
          this.__itemSelected();
        }, this);
      };
      this.setDelegate(delegate);
    },

    getSelectedFile: function() {
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
    },

    __isFile: function(item) {
      let isFile = false;
      if (item["set"+qx.lang.String.firstUp("fileId")]) {
        isFile = true;
      }
      return isFile;
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
    }
  }
});
