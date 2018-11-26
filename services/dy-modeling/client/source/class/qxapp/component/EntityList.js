/* eslint no-warning-comments: "off" */
/* eslint no-underscore-dangle: ["error", { "allowAfterThis": true, "enforceInMethodNames": true, "allow": ["__widgetChildren"] }] */

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

    populateTree: function() {
      let data = {
        label: "Model",
        entityId: "root",
        path: "Model",
        checked: true,
        children: []
      };
      let model = qx.data.marshal.Json.createModel(data, true);
      // configure model for triState usage
      this.configureTriState(model);

      // data binding
      this.__tree.setModel(model);
      this.__tree.setDelegate({
        createItem: () => new qxapp.component.EntityListItem(),
        bindItem: (c, item, id) => {
          c.bindDefaultProperties(item, id);
          c.bindProperty("entityId", "entityId", null, item, id);
          c.bindProperty("path", "path", null, item, id);
          c.bindProperty("checked", "checked", null, item, id);
        },
        configureItem: item => {
          item.addListener("visibilityChanged", e => {
            this.fireDataEvent("visibilityChanged", e.getData());
          }, this);
        }
      });
    },

    // from http://www.qooxdoo.org/current/demobrowser/#virtual~Tree_Columns.html
    configureTriState: function(item) {
      item.getModel = function() {
        return this;
      };

      if (item.getChildren != null) { // eslint-disable-line no-eq-null
        let children = item.getChildren();
        for (let i = 0; i < children.getLength(); i++) {
          let child = children.getItem(i);
          this.configureTriState(child);

          // bind parent with child
          item.bind("checked", child, "checked", {
            converter: function(value, child2) {
              // when parent is set to null than the child should keep it's value
              if (value === null) {
                return child2.getChecked();
              }
              return value;
            }
          });

          // bind child with parent
          child.bind("checked", item, "checked", {
            converter: function(value, parent) {
              let children2 = parent.getChildren().toArray();
              let isAllChecked = children2.every(function(item2) {
                return item2.getChecked();
              });
              let isOneChecked = children2.some(function(item2) {
                return item.getChecked() || item2.getChecked() === null;
              });
              // Set triState (on parent node) when one child is checked
              if (isOneChecked) {
                return isAllChecked ? true : null;
              }
              return false;
            }
          });
        }
      }
    },

    __onSelectionChanged: function(e) {
      this.fireDataEvent("selectionChanged", this.getSelectedEntityIds());
    },

    __removeEntityPressed: function() {
      let selectedIds = this.getSelectedEntityIds();
      for (let i = 0; i < selectedIds.length; i++) {
        this.fireDataEvent("removeEntityRequested", selectedIds[i]);
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

    addEntity: function(entityId, name, path) {
      let model = this.__tree.getModel();
      let newItem = {
        entityId: entityId,
        label: name,
        path: path ? path : "Model/"+name,
        checked: true
      };
      let newItemModel = qx.data.marshal.Json.createModel(newItem, true);
      model.getChildren().push(newItemModel);
      this.configureTriState(model);
      this.__tree.setModel(model);
      let newSelection = new qx.data.Array([newItemModel]);
      this.__tree.setSelection(newSelection);
    },

    removeEntity: function(uuid) {
      const model = this.__tree.getModel();
      let children = model.getChildren().toArray();
      for (let i = 0; i < children.length; i++) {
        if (uuid === children[i].getEntityId()) {
          model.getChildren().remove(children[i]);
        }
      }
    },

    onEntitySelectedChanged: function(uuids) {
      if (uuids === null) {
        this.__tree.resetSelection();
      } else {
        const model = this.__tree.getModel();
        let selected = new qx.data.Array();
        let children = model.getChildren().toArray();
        for (let i = 0; i < children.length; i++) {
          if (uuids.includes(children[i].getEntityId())) {
            selected.push(children[i]);
          }
        }
        this.__tree.setSelection(selected);
      }
    }
  }
});
