/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that shows an image well centered and scaled.
 * | _________________________________ |
 * | XXXXXXXXXXXX______ X GB__________ |
 * |___________________________________|
 */
qx.Class.define("osparc.workbench.DiskUsageIndicator", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    const lowDiskSpacePreferencesSettings = osparc.Preferences.getInstance();
    this.__lowDiskThreshold = lowDiskSpacePreferencesSettings.getLowDiskSpaceThreshold();
    this.__prevDiskUsageStateList = [];
    const layout = this.__layout = new qx.ui.layout.VBox(2);

    this._setLayout(layout);
    // Subscribe to disk space threshold - Default 5GB
    lowDiskSpacePreferencesSettings.addListener("changeLowDiskSpaceThreshold", e => {
      this.__lowDiskThreshold = e.getData();
    }, this)
    // Subscribe to node selected node
    this.addListener("changeSelectedNode", e => this.__applySelectedNode(e.getData()), this);
    // Subscribe to nodes in the workbench
    this.addListener("changeCurrentNode", e => this.__applyCurrentNode(e.getData()), this);
  },

  properties: {
    currentNode: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: true,
      event: "changeCurrentNode",
      apply: "__applyCurrentNode",
    },
    selectedNode: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: true,
      event: "changeSelectedNode",
      apply: "__applySelectedNode",
    }
  },

  members: {
    __indicator: null,
    __label: null,
    __lowDiskThreshold: null,
    __prevDiskUsageStateList: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "disk-indicator": {
          control = new qx.ui.container.Composite(
            new qx.ui.layout.VBox().set({
              alignY: "middle",
              alignX: "center"
            })
          ).set({
            decorator: "indicator-border",
            padding: [2, 10],
            margin: 4,
            alignY: "middle",
            allowShrinkX: false,
            allowShrinkY: false,
            allowGrowX: true,
            allowGrowY: false,
            toolTipText: this.tr("Disk usage"),
            // visibility: "excluded"
          });
          this._add(control)
          break;
        }
        case "disk-indicator-label": {
          const indicator = this.getChildControl("disk-indicator")
          control = new qx.ui.basic.Label().set({
            value: "5GB",
            font: "text-13",
            textColor: "contrasted-text-light",
            alignX: "center",
            alignY: "middle",
            rich: false
          })
          indicator.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __applyCurrentNode: function(node, prevNode) {
      // Unsubscribe from previous node's disk usage data
      if (prevNode) {
        this._unsubscribe(prevNode.getNodeId())
      }

      // Subscribe to disk usage data for the new node
      this._subscribe(node);
    },


    __applySelectedNode: function(node, prevNode) {
      // Unsubscribe from previous node's disk usage data
      if (prevNode) {
        this._unsubscribe(prevNode.getNodeId())
      }

      // Subscribe to disk usage data for the new node
      this._subscribe(node);
    },

    _subscribe: function(node) {
      osparc.workbench.DiskUsageController.getInstance().subscribe(node.getNodeId(), e => {
        console.log("subscribe", e["node_id"], node.getNodeId())
        this.__updateDiskIndicator(e);
      }, node);
    },

    _unsubscribe: function(nodeId) {
      osparc.workbench.DiskUsageController.getInstance().unsubscribe(nodeId, this.__updateDiskIndicator);
    },

    getIndicatorColor: function(freeSpace) {
      const warningSize = osparc.utils.Utils.gBToBytes(this.__lowDiskThreshold); // 5 GB Default
      const criticalSize = osparc.utils.Utils.gBToBytes(0.01); // 0 GB
      let color = qx.theme.manager.Color.getInstance().resolve("success");

      if (freeSpace <= criticalSize) {
        color = qx.theme.manager.Color.getInstance().resolve("error")
      } else if (freeSpace <= warningSize) {
        color = qx.theme.manager.Color.getInstance().resolve("warning")
      } else {
        color = qx.theme.manager.Color.getInstance().resolve("success")
      }
      return color
    },

    __updateDiskIndicator: function(diskUsage) {
      if (!diskUsage) {
        return;
      }
      const indicator = this.getChildControl("disk-indicator");
      const indicatorLabel = this.getChildControl("disk-indicator-label");
      const usage = diskUsage["usage"]["/"]
      const warningColor = this.getIndicatorColor(usage.free);
      const progress = `${usage["used_percent"]}%`;
      const labelDiskSize = osparc.utils.Utils.bytesToSize(usage.free);
      const color1 = warningColor;
      const bgColor = qx.theme.manager.Color.getInstance().resolve("tab_navigation_bar_background_color");
      const color2 = qx.theme.manager.Color.getInstance().resolve("info");

      indicator.getContentElement().setStyles({
        "background-color": bgColor,
        "background": `linear-gradient(90deg, ${color1} ${progress}, ${color2} ${progress})`,
      });

      indicatorLabel.setValue(`${labelDiskSize} Free`);
      const indicatorIsVisible = (this.getSelectedNode() && this.getSelectedNode().getNodeId() === diskUsage["node_id"]) || (this.getCurrentNode() && this.getCurrentNode().getNodeId() === diskUsage["node_id"]);
      indicator.setVisibility(indicatorIsVisible ? "visible" : "excluded");
    },

    // Cleanup method
    destruct: function() {
      const currentNode = this.getCurrentNode();
      const selectedNode = this.getSelectedNode();
      if (currentNode) {
        this._unsubscribe(currentNode.getNodeId())
      }
      if (selectedNode) {
        this._unsubscribe(selectedNode.getNodeId())
      }
    }
  }
});
