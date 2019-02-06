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

qx.Class.define("qxapp.component.widget.InputsMapperTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    isDir: {
      check: "Boolean",
      nullable: false,
      init: true
    },

    isRoot: {
      check: "Boolean",
      nullable: false,
      init: false
    },

    nodeKey: {
      check: "String",
      nullable: false
    },

    portKey: {
      check: "String",
      nullable: false
    }
  }
});
