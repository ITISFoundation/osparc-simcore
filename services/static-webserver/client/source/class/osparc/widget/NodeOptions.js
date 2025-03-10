/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.widget.NodeOptions", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {osparc.data.model.Node} Node owning the widget
    */
  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(15));

    // it will become visible if children are added
    this.exclude();

    this.setNode(node);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    }
  },

  members: {
    // overridden
    _afterAddChild: function() {
      this.show();
    },

    buildLayout: async function() {
      const node = this.getNode();

      const sections = [];
      let showStartStopButton = false;

      // Tier Selection
      if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
        const tierSelectionView = new osparc.node.TierSelectionView(node);
        sections.push(tierSelectionView);

        if (node.isDynamic()) {
          showStartStopButton = true;
        }
      }

      // Life Cycle
      if (
        node.isDynamic() &&
        (node.isUpdatable() || node.isDeprecated() || node.isRetired())
      ) {
        const lifeCycleView = new osparc.node.LifeCycleView(node);
        sections.push(lifeCycleView);

        showStartStopButton = true;
      }

      // Boot Options
      if (node.hasBootModes()) {
        const bootOptionsView = new osparc.node.BootOptionsView(node);
        sections.push(bootOptionsView);

        showStartStopButton = true;
      }

      // Update Resource Limits
      if (
        await osparc.data.Permissions.getInstance().checkCanDo("override_services_specifications") &&
        (node.isComputational() || node.isDynamic())
      ) {
        const updateResourceLimitsView = new osparc.node.UpdateResourceLimitsView(node);
        sections.push(updateResourceLimitsView);

        showStartStopButton |= node.isDynamic();
      }

      if (showStartStopButton) {
        // Only available to dynamic services
        const instructions = new qx.ui.basic.Label(this.tr("To proceed with the following actions, the service needs to be Stopped.")).set({
          font: "text-13",
          rich: true,
          wrap: true
        });
        this._add(instructions);

        const startStopButton = new osparc.node.StartStopButton();
        startStopButton.setNode(node);
        this._add(startStopButton);

        startStopButton.getChildControl("stop-button").bind("visibility", instructions, "visibility");
      }

      sections.forEach(section => this._add(section));
    }
  }
});
