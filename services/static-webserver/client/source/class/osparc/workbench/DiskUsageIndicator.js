/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Julian Querido (jsaq007)

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
    this.__lastDiskUsage = {};

    this._setLayout(new qx.ui.layout.VBox());

    // hide until some info comes
    this.hide();

    // Subscribe to disk space threshold - Default 5GB
    lowDiskSpacePreferencesSettings.addListener("changeLowDiskSpaceThreshold", e => {
      this.__lowDiskThreshold = e.getData();
      this.__updateDiskIndicator();
    }, this);
  },

  properties: {
    currentNode: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: true,
      event: "changeCurrentNode",
      apply: "__applyCurrentNode",
    }
  },

  members: {
    __lowDiskThreshold: null,
    __lastDiskUsage: null,

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
          });
          this._add(control)
          break;
        }
        case "disk-indicator-label": {
          const indicator = this.getChildControl("disk-indicator")
          control = new qx.ui.basic.Label().set({
            value: "",
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

    _subscribe: function(node) {
      osparc.workbench.DiskUsageController.getInstance().subscribe(node.getNodeId(), e => {
        this.__updateDiskIndicator(e);
      });
    },

    _unsubscribe: function(nodeId) {
      osparc.workbench.DiskUsageController.getInstance().unsubscribe(nodeId, this.__updateDiskIndicator);
    },

    __getIndicatorColor: function(freeSpace) {
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
      this.show();
      if (diskUsage && diskUsage["node_id"]) {
        this.__lastDiskUsage[diskUsage["node_id"]] = diskUsage;
      }

      const indicator = this.getChildControl("disk-indicator");

      const currentNode = this.getCurrentNode();
      if (currentNode) {
        indicator.setVisibility("visible");
      } else {
        indicator.setVisibility("exclude");
        return;
      }

      const currentNodeId = currentNode.getNodeId();

      if (!diskUsage && (currentNodeId in this.__lastDiskUsage)) {
        diskUsage = this.__lastDiskUsage[currentNodeId];
      }
      if (!diskUsage) {
        return;
      }

      const diskHostUsage = diskUsage["usage"]["HOST"]
      let color1 = this.__getIndicatorColor(diskHostUsage.free);
      let progress = `${diskHostUsage["used_percent"]}%`;
      let labelDiskSize = osparc.utils.Utils.bytesToSize(diskHostUsage.free);
      let toolTipText = this.tr("Disk usage");
      if ("STATES_VOLUMES" in diskUsage["usage"]) {
        const diskVolsUsage = diskUsage["usage"]["STATES_VOLUMES"];
        if (diskVolsUsage["used_percent"] > diskHostUsage["used_percent"]) {
          // "STATES_VOLUMES" is more critical so it takes over
          color1 = this.__getIndicatorColor(diskVolsUsage.free);
          progress = `${diskVolsUsage["used_percent"]}%`;
          labelDiskSize = osparc.utils.Utils.bytesToSize(diskVolsUsage.free);
        }
        toolTipText = this.tr("Disk usage") + "<br>";
        toolTipText += this.tr("Data storage: ") + osparc.utils.Utils.bytesToSize(diskVolsUsage.free) + "<br>";
        toolTipText += this.tr("I/O storage: ") + osparc.utils.Utils.bytesToSize(diskHostUsage.free) + "<br>";
      }
      const bgColor = qx.theme.manager.Color.getInstance().resolve("tab_navigation_bar_background_color");
      const color2 = qx.theme.manager.Color.getInstance().resolve("progressive-progressbar-background");
      indicator.getContentElement().setStyles({
        "background-color": bgColor,
        "background": `linear-gradient(90deg, ${color1} ${progress}, ${color2} ${progress})`,
        "border-color": color1
      });
      indicator.set({
        toolTipText
      });

      const indicatorLabel = this.getChildControl("disk-indicator-label");
      indicatorLabel.setValue(`${labelDiskSize} Free`);
    },

    // Cleanup method
    destruct: function() {
      const currentNode = this.getCurrentNode();
      if (currentNode) {
        this._unsubscribe(currentNode.getNodeId())
      }
    }
  }
});
