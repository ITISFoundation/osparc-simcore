/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.node.BootOptionsView", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base();

    this._setLayout(new qx.ui.layout.VBox(10));

    if (node) {
      this.setNode(node);
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode"
    }
  },

  members: {
    __applyNode: function(node) {
      if (node.hasBootModes()) {
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Boot Options")).set({
        font: "text-14"
      }));

      const node = this.getNode();

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const stopButton = new qx.ui.form.Button().set({
        label: this.tr("Stop"),
        icon: "@FontAwesome5Solid/stop/14",
        enabled: false
      });
      node.getStatus().bind("interactive", stopButton, "enabled", {
        converter: state => state === "ready"
      });
      node.attachExecuteHandlerToStopButton(stopButton);
      buttonsLayout.add(stopButton);

      const nodeMetaData = node.getMetaData();
      const workbenchData = node.getWorkbench().serialize();
      const nodeId = node.getNodeId();
      const bootModeSB = osparc.data.model.Node.getBootModesSelectBox(nodeMetaData, workbenchData, nodeId);
      bootModeSB.addListener("changeSelection", e => {
        const newBootModeId = e.getData()[0].bootModeId;
        console.log("update me", newBootModeId);
        // this.__updateBootMode(nodeId, newBootModeId);
      }, this);
      buttonsLayout.add(bootModeSB);

      this._add(buttonsLayout);
    }
  }
});
