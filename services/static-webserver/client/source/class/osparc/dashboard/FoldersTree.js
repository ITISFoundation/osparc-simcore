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

qx.Class.define("osparc.dashboard.FoldersTree", {
  extend: qx.ui.tree.VirtualTree,

  construct: function() {
    const rootFolder = this.self().createNewEntry(null);
    const root = qx.data.marshal.Json.createModel(rootFolder, true);
    this.__fetchChildren(root);

    this.base(arguments, root, "label", "children");

    this.set({
      openMode: "dbltap",
      decorator: "no-border",
      font: "text-14",
      showLeafs: true,
      paddingLeft: -10,
    });

    this.__initTree();
  },

  events: {
    "selectionChanged": "qx.event.type.Event" // tap
  },

  statics: {
    createNewEntry: function(folder) {
      return {
        folderId: folder ? folder.getFolderId() : null,
        label: folder ? folder.getName() : "Home",
        children: [
          this.self().getLoadingData()
        ],
        loaded: false,
      };
    },

    getLoadingData: function() {
      return {
        folderId: -1,
        label: "Loading...",
        children: [],
        icon: "@FontAwesome5Solid/circle-notch/12",
        loaded: false,
      };
    },

    addLoadingChild: function(parentModel) {
      const loadingModel = qx.data.marshal.Json.createModel(this.self().getLoadingData(), true);
      parentModel.getChildren().append(loadingModel);
    },

    removeLoadingChild: function(parent) {
      for (let i = parent.getChildren().getLength() - 1; i >= 0; i--) {
        if (parent.getChildren().toArray()[i].getLabel() === "Loading...") {
          parent.getChildren().splice(i, 1);
        }
      }
    }
  },

  members: {
    __initTree: function() {
      const that = this;
      this.setDelegate({
        createItem: () => new osparc.dashboard.FolderTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("folderId", "model", null, item, id);
          c.bindProperty("", "open", {
            converter(value, _, __, target) {
              const isOpen = target.isOpen();
              if (isOpen && !value.getLoaded()) {
                // eslint-disable-next-line no-underscore-dangle
                that.__fetchChildren(value);
              }
              return isOpen;
            }
          }, item, id);
        },
        configureItem: item => {
          item.addListener("tap", () => this.fireDataEvent("selectionChanged", item.getModel()), this);
        },
        sorter: (a, b) => {
          const aLabel = a.getLabel();
          if (aLabel === -1) {
            return 1;
          }
          const bLabel = b.getLabel();
          if (bLabel === -1) {
            return -1;
          }
          return aLabel - bLabel;
        }
      });
    },

    __fetchChildren: function(parentModel) {
      parentModel.setLoaded(true);

      const folderId = parentModel.getFolderId ? parentModel.getFolderId() : parentModel.getModel();
      osparc.store.Folders.getInstance().fetchFolders(folderId)
        .then(folders => {
          this.self().removeLoadingChild(parentModel);
          folders.forEach(folder => {
            const folderData = this.self().createNewEntry(folder);
            const folderModel = qx.data.marshal.Json.createModel(folderData, true);
            parentModel.getChildren().append(folderModel);
          });
        })
        .catch(console.error);
    }
  }
});
