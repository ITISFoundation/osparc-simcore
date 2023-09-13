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

qx.Class.define("osparc.node.BootOptionsView", {
  extend: osparc.node.ServiceOptionsView,

  events: {
    "bootModeChanged": "qx.event.type.Event"
  },

  members: {
    _applyNode: function(node) {
      if (node.hasBootModes()) {
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Boot Options")).set({
        font: "text-14"
      }));

      const instructionsMsg = this.tr("Please Stop the Service and then change the Boot Mode");
      const instructionsLabel = new qx.ui.basic.Label(instructionsMsg).set({
        rich: true
      });
      this._add(instructionsLabel);

      const node = this.getNode();

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const nodeMetaData = node.getMetaData();
      const workbenchData = node.getWorkbench().serialize();
      const nodeId = node.getNodeId();
      const bootModeSB = osparc.data.model.Node.getBootModesSelectBox(nodeMetaData, workbenchData, nodeId);
      node.getStatus().bind("interactive", bootModeSB, "enabled", {
        converter: interactive => interactive === "idle"
      });
      bootModeSB.addListener("changeSelection", e => {
        buttonsLayout.setEnabled(false);
        const newBootModeId = e.getData()[0].bootModeId;
        node.setBootOptions({
          "boot_mode": newBootModeId
        });
        setTimeout(() => {
          buttonsLayout.setEnabled(true);
          node.requestStartNode();
          this.fireEvent("bootModeChanged");
        }, osparc.desktop.StudyEditor.AUTO_SAVE_INTERVAL*2);
      }, this);
      buttonsLayout.add(bootModeSB);

      this._add(buttonsLayout);
    }
  }
});
