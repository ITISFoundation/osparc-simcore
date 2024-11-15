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

  members: {
    _applyNode: function(node) {
      if (node.hasBootModes()) {
        this.__populateLayout();
      }

      this.base(arguments, node);
    },

    __populateLayout: function() {
      this._removeAll();

      this._add(new qx.ui.basic.Label(this.tr("Boot Options")).set({
        font: "text-14"
      }));

      const node = this.getNode();

      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      const nodeMetadata = node.getMetaData();
      const workbenchData = node.getWorkbench().serialize();
      const nodeId = node.getNodeId();
      const bootModeSB = osparc.data.model.Node.getBootModesSelectBox(nodeMetadata, workbenchData, nodeId);
      node.getStatus().bind("interactive", bootModeSB, "enabled", {
        converter: interactive => interactive === "idle"
      });
      bootModeSB.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          buttonsLayout.setEnabled(false);
          const newBootModeId = selection[0].bootModeId;
          node.setBootOptions({
            "boot_mode": newBootModeId
          });
          node.fireEvent("updateStudyDocument");
          setTimeout(() => {
            buttonsLayout.setEnabled(true);
            node.requestStartNode();
          }, osparc.desktop.StudyEditor.AUTO_SAVE_INTERVAL);
        }
      }, this);
      buttonsLayout.add(bootModeSB);

      this._add(buttonsLayout);
    }
  }
});
