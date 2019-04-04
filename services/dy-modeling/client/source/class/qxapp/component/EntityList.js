/* eslint no-warning-comments: "off" */
/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "enforceInMethodNames": true, "allow": ["__widgetChildren"] }] */

const ROOT_ID = "00000000-0000-0000-0000-000000000000";

qx.Class.define("qxapp.component.EntityList", {
  extend: qx.ui.window.Window,

  include: [qx.locale.MTranslation],

  construct: function() {
    this.base(arguments, this.tr("Entity List"));

    this.set({
      contentPadding: 0,
      width: 250,
      height: 400,
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      layout: new qx.ui.layout.VBox()
    });

    let scroller = new qx.ui.container.Scroll();
    this.add(scroller, {
      flex: 1
    });

    // create and add the tree
    this.__tree = new qx.ui.tree.VirtualTree(null, "label", "children");
    this.__tree.setSelectionMode("multi");
    this.populateTree();
    this.__tree.getSelection().addListener("change", this.__onSelectionChanged.bind(this));

    let removeBtn = new qx.ui.form.Button(this.tr("Remove entity"));
    removeBtn.set({
      width: 100,
      height: 30
    });
    removeBtn.addListener("execute", this.__removeEntityPressed.bind(this));

    this.__progressBar = new qx.ui.indicator.ProgressBar();

    scroller.add(this.__tree);
    this.add(removeBtn);
  },

  events: {
    "removeEntityRequested": "qx.event.type.Data",
    "selectionChanged": "qx.event.type.Data",
    "visibilityChanged": "qx.event.type.Data"
  },

  members: {
    __tree: null,
    __progressBar: null,
    __treeMap: null,

    modelLoading: function() {
      if (this.indexOf(this.__progressBar) != -1) {
        this.remove(this.__progressBar);
      }

      this.add(this.__progressBar);
    },

    initiateProgress: function(total) {
      this.__progressBar.setMaximum(total);
      this.__progressBar.setValue(0);
    },

    incrementProgress: function(value) {
      this.__progressBar.setValue(this.__progressBar.getValue() + value);
    },

    modelLoaded: function() {
      if (this.indexOf(this.__progressBar) != -1) {
        this.remove(this.__progressBar);
      }
    },

    populateTree: function() {
      let data = {
        label: "Model",
        entityId: ROOT_ID,
        pathId: ROOT_ID,
        pathLabel: "Model",
        checked: true,
        children: []
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      this.__treeMap = {
        "root": model
      };

      // data binding
      this.__tree.setModel(model);
      this.__tree.setDelegate({
        createItem: () => new qxapp.component.EntityListItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("entityId", "entityId", null, item, id);
          c.bindProperty("pathId", "pathId", null, item, id);
          c.bindProperty("pathLabel", "pathLabel", null, item, id);
          c.bindProperty("checked", "checked", null, item, id);
          c.bindPropertyReverse("checked", "checked", null, item, id);
        },
        configureItem: item => {
          item.addListener("visibilityChanged", e => {
            this.fireDataEvent("visibilityChanged", e.getData());
          }, this);
        }
      });
    },

    __onSelectionChanged: function(e) {
      this.fireDataEvent("selectionChanged", this.getSelectedEntityIds());
    },

    __removeEntityPressed: function() {
      let selectedIds = this.getSelectedEntityIds();
      if (selectedIds.includes(ROOT_ID)) {
        return;
      }
      for (let i = 0; i < selectedIds.length; i++) {
        if (this.__findUuidInLeaves(selectedIds[i])) {
          // Leaf
          this.fireDataEvent("removeEntityRequested", selectedIds[i]);
        } else {
          // Folder
          // TODO: Delete folders
        }
      }
    },

    __getSelectedItems: function() {
      return this.__tree.getSelection().toArray();
    },

    getSelectedEntityId: function() {
      let selectedItems = this.__getSelectedItems();
      if (selectedItems.length > 0) {
        return selectedItems[0].getEntityId();
      }
      return null;
    },

    getSelectedEntityIds: function() {
      let selectedIds = [];
      let selectedItems = this.__getSelectedItems();
      for (let i = 0; i < selectedItems.length; i++) {
        selectedIds.push(selectedItems[i].getEntityId());
      }
      return selectedIds;
    },

    addEntity: function(name, entityId, pathId, pathName) {
      let newItem = {
        entityId: entityId,
        pathId: pathId ? pathId : "root/"+entityId,
        pathLabel: pathName ? pathName : "Model/"+name,
        checked: true
      };
      let pathSplit = newItem.pathId.split("/");
      newItem.label = name ? name : pathSplit[pathSplit.length-1];
      // create first the folders if do not exist yet
      let parent = this.__tree.getModel();
      // console.log(parent);
      let tm = this.__treeMap;
      pathSplit.forEach(key => {
        if (!tm[key]) {
          let kid = tm[key] = qx.data.marshal.Json.createModel(
            {
              label: key,
              entityId: null,
              pathId: null,
              pathLabel: null,
              checked: true,
              children: []
            },
            true
          );
          parent.getChildren().push(kid);

          parent.bind("checked", kid, "checked", {
            converter: valueParent => {
              if (valueParent === null) {
                return kid.getChecked();
              }
              return valueParent;
            }
          });
          let myParent = parent;
          kid.bind("checked", myParent, "checked", {
            converter: () => {
              let kids = myParent.getChildren().toArray();
              let isAllChecked = kids.every(item => item.getChecked());
              let isOneChecked = kids.some(item => item.getChecked());
              return (
                // eslint-disable-next-line no-nested-ternary
                isAllChecked ? true :
                  isOneChecked ? null : false
              );
            }
          });
        }
        parent = tm[key];
      });
      parent.set(newItem);
    },


    __getLeafList: function(item, leaves) {
      if (item.getChildren == null) { // eslint-disable-line no-eq-null
        leaves.push(item);
      } else {
        for (let i = 0; i < item.getChildren().length; i++) {
          this.__getLeafList(item.getChildren().toArray()[i], leaves);
        }
      }
    },

    __findUuidInLeaves: function(uuid) {
      let parent = this.__tree.getModel();
      let list = [];
      this.__getLeafList(parent, list);
      for (let j = 0; j < list.length; j++) {
        if (uuid === list[j].getEntityId()) {
          return list[j];
        }
      }
      return null;
    },

    __getParents: function(item) {
      let parents = [this.__tree.getModel()];
      if (item) {
        let pathSplitted = item.getPathId().split("/");
        let parent = this.__tree.getModel();
        for (let i = 1; i < pathSplitted.length-1; i++) {
          let children = parent.getChildren().toArray();
          for (let j = 0; j < children.length; j++) {
            if (children[j].getEntityId() === pathSplitted[i]) {
              parents.push(children[j]);
              parent = children[j];
              break;
            }
          }
        }
      }
      return parents;
    },

    removeEntity: function(uuid) {
      let item = this.__findUuidInLeaves(uuid);
      if (item) {
        // Leave
        let pathSplitted = item.getPathId().split("/");
        let parent = this.__tree.getModel();
        for (let i = 1; i < pathSplitted.length-1; i++) {
          let children = parent.getChildren().toArray();
          for (let j = 0; j < children.length; j++) {
            if (children[j].getEntityId() === pathSplitted[i]) {
              parent = children[j];
              break;
            }
          }
        }
        let children = parent.getChildren().toArray();
        for (let i = 0; i < children.length; i++) {
          if (uuid === children[i].getEntityId()) {
            parent.getChildren().remove(children[i]);
          }
        }
      }
    },

    onEntitySelectedChanged: function(uuids) {
      if (uuids === null) {
        this.__tree.resetSelection();
      } else {
        let selected = new qx.data.Array();
        for (let i = 0; i < uuids.length; i++) {
          const uuid = uuids[i];
          let item = this.__findUuidInLeaves(uuid);
          if (item) {
            selected.push(item);
            // TODO: open parent folders
            let parents = this.__getParents(item);
            console.log(parents);
          }
        }
        this.__tree.setSelection(selected);
      }
    }
  }
});
