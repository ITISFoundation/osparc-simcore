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
    this.base(arguments, null, "label", "children");

    this.set({
      openMode: "none",
      contentPadding: 0,
      paddingLeft: -10,
      decorator: "no-border",
      font: "text-14"
    });

    this.__initTree();
    this.__populateTree();
  },

  events: {
    "selectionChanged": "qx.event.type.Event" // tap
  },

  statics: {
    addLoadingChild: function(parentModel) {
      const loadingModel = qx.data.marshal.Json.createModel({
        label: "Loading...",
        children: [],
        icon: "@FontAwesome5Solid/circle-notch/12"
      }, true);
      parentModel.getChildren().removeAll();
      parentModel.getChildren().append(loadingModel);
    }
  },

  members: {
    __initTree: function() {
      this.setDelegate({
        createItem: () => new qx.ui.tree.VirtualTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("folderId", "model", null, item, id);
          c.bindProperty("name", "label", null, item, id);
        },
        configureItem: item => {
          item.addListener("tap", () => this.fireDataEvent("selectionChanged", item.getModel()), this);

          const openButton = item.getChildControl("open");
          openButton.addListener("tap", () => {
            this.__fetchChildren(item);
          });
          // OM remove this
          item.addListener("dbltap", () => this.__fetchChildren(item), this);
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

    __populateTree: function() {
      const rootFolder = {
        folderId: null,
        name: "Home",
        children: []
      };
      const rootModel = qx.data.marshal.Json.createModel(rootFolder, true);
      this.setModel(rootModel);

      this.__fetchChildren(rootModel);
    },

    __fetchChildren: function(parentModel) {
      this.self().addLoadingChild(parentModel);

      const folderId = parentModel.getFolderId ? parentModel.getFolderId() : parentModel.getModel();
      osparc.store.Folders.getInstance().fetchFolders(folderId)
        .then(folders => {
          parentModel.getChildren().removeAll();
          folders.forEach(folder => {
            const folderData = {
              folderId: folder.getFolderId(),
              name: folder.getName(),
              children: []
            };
            const folderModel = qx.data.marshal.Json.createModel(folderData, true);
            this.self().addLoadingChild(folderModel);
            parentModel.getChildren().append(folderModel);
          });
        });
    }
  }
});
