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

qx.Class.define("osparc.component.node.LifeCycleView", {
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
      if (node.isDeprecated() || node.isRetired()) {
        this.__populateLayout();
      }
    },

    __populateLayout: function() {
      this._removeAll();
      const node = this.getNode();

      const chip = node.isDeprecated() ? osparc.utils.StatusUI.createServiceDeprecatedChip() : osparc.utils.StatusUI.createServiceRetiredChip();
      this._add(chip);

      if (node.isDeprecated()) {
        const deprecateDateLabel = new qx.ui.basic.Label(osparc.utils.Services.getDeprecationDateText(node.getMetaData())).set({
          rich: true
        });
        this._add(deprecateDateLabel);
      }

      const instructionsMsg = node.isDeprecated() ? osparc.utils.Services.DEPRECATED_DYNAMIC_INSTRUCTIONS : osparc.utils.Services.RETIRED_DYNAMIC_INSTRUCTIONS;
      const instructionsLabel = new qx.ui.basic.Label(instructionsMsg).set({
        rich: true
      });
      this._add(instructionsLabel);


      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));

      const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(null, node.getKey(), node.getVersion());
      const autoUpdatable = node.getVersion() !== latestCompatibleMetadata["version"];

      const stopButton = new qx.ui.form.Button().set({
        label: this.tr("Stop"),
        icon: "@FontAwesome5Solid/stop/14",
        enabled: false
      });
      node.getStatus().bind("interactive", stopButton, "enabled", {
        converter: state => state === "ready"
      });
      buttonsLayout.add(stopButton);

      const updateButton = new osparc.ui.form.FetchButton().set({
        label: this.tr("Update"),
        icon: "@MaterialIcons/update/14",
        backgroundColor: "strong-main"
      });
      stopButton.bind("enabled", updateButton, "enabled", {
        converter: enabled => !enabled && autoUpdatable
      });

      buttonsLayout.add(updateButton);

      this._add(buttonsLayout);
    }
  }
});
