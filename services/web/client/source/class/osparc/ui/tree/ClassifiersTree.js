/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

// based on CheckboxTree.js
// ToDo convert this Class into a Mixin

qx.Class.define("osparc.ui.tree.ClassifiersTree", {
  extend: qx.ui.tree.VirtualTree,
  construct: function(data) {
    this.base(arguments, this.__createModel(data), "label", "children", "open");
    this.set({
      delegate: {
        createItem: function() {
          return new osparc.ui.tree.ClassifiersTreeItem();
        },
        bindItem: function(controller, item, id) {
          controller.bindDefaultProperties(item, id);
          controller.bindProperty("description", "description", null, item, id);
          controller.bindProperty("url", "url", null, item, id);
        },
        configureItem: function(item) {
          item.setSelectable(false);
        }
      },
      hideRoot: true,
      decorator: "no-border",
      selectionMode: "multi"
    });
  },

  members: {
    __createModel: function(data) {
      this.__extendData(data);
      const model = qx.data.marshal.Json.createModel(data, true);
      return model;
    },

    __extendData: function(data) {
      data.open = data.open || true;
      data.children = data.children || [];
      data.children.forEach(child => this.__extendData(child));
    }
  }
});
