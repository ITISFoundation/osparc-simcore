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
    this.base(arguments, null, "name", "children");

    this.set({
      openMode: "none",
      contentPadding: 0,
      padding: 0,
      decorator: "no-border",
      font: "text-14"
    });

    this.__populateTree();
  },

  events: {
    "selectionChanged": "qx.event.type.Event" // tap
  },

  properties: {
    currentFolderId: {
      check: "Number",
      nullable: true,
      init: null,
      event: "changeCurrentFolderId",
      apply: "__applyCurrentFolderId"
    }
  },

  statics: {
    addLoadingChild: function(parent) {
      const loadingModel = qx.data.marshal.Json.createModel({
        label: "Loading...",
        location: null,
        path: null,
        children: [],
        icon: "@FontAwesome5Solid/circle-notch/12"
      }, true);
      parent.getChildren().append(loadingModel);
    },

    removeLoadingChild: function(parent) {
      for (let i = parent.getChildren().length - 1; i >= 0; i--) {
        if (parent.getChildren().toArray()[i].getLabel() === "Loading...") {
          parent.getChildren().toArray()
            .splice(i, 1);
        }
      }
    }
  },

  members: {
    __populateTree: function() {
      this.setDelegate({
        createItem: () => new osparc.dashboard.FolderTreeItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("folderId", "model", null, item, id);
          c.bindProperty("name", "name", null, item, id);
        },
        configureItem: item => {
          item.addListener("tap", () => this.fireDataEvent("selectionChanged", item.getModel()), this);

          const openButton = item.getChildControl("open");
          openButton.addListener("tap", () => {
          });
        },
        sorter: (a, b) => {
          const aName = a.getName();
          if (aName === -1) {
            return 1;
          }
          const bName = b.getName();
          if (bName === -1) {
            return -1;
          }
          return aName - bName;
        }
      });

      const rootFolder = {
        folderId: null,
        name: "Home",
        children: []
      };
      const root = qx.data.marshal.Json.createModel(rootFolder, true);
      this.setModel(root);

      this.self().addLoadingChild(this.getModel());
    },

    __applyCurrentFolderId: function() {
    }
  }
});
