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
    }
  }
});
