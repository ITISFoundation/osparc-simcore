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
 * VirtualTreeItem used mainly by SimulatorTree
 *
 */

qx.Class.define("qxapp.component.widget.simulator.SimulatorTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    key: {
      check: "String",
      nullable: true
    },

    version: {
      check: "String",
      nullable: true
    },

    metadata: {
      check: "Object",
      nullable: true
    },

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

    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    }
  },

  members: {
    createNode: function(workbench) {
      const node = new qxapp.data.model.Node(workbench, this.getKey(), this.getVersion());
      this.setNode(node);

      const metadata = this.getMetadata();
      if (metadata) {
        const metadata2 = qx.util.Serializer.toNativeObject(metadata);
        node.initMetaData(metadata2);
        this.setLabel(node.getLabel());
      }
    }
  }
});
