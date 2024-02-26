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
    this.__testDiskUsage = [];
    const layout = this.__layout = new qx.ui.layout.VBox(2);
    this._setLayout(layout);
    // this._applyCurrentNode(this.getCurrentNode());

    this.addListener("changeSelectedNode", e => {
      const node = e.getData();
      if (node !== this.getCurrentNode()) {
        osparc.workbench.DiskUsageController.getInstance().subscribe(node.getNodeId(), data => {
          if (node.getNodeId() === data["node_id"]) {
            this.__onNewUsageData(node, data);
          } else {
            console.log("changeSelectedNode", data)
          }
        })
      } else {
        osparc.workbench.DiskUsageController.getInstance().unsubscribe(node.getNodeId(), data => {
          console.log("Exiting...", this.getCurrentNode().getNodeId())
        })
      }
    }, this);
  },

  properties: {
    currentNode: {
      check : "osparc.data.model.Node",
      init : null,
      nullable : true,
      event : "changeCurrentNode",
      apply: "_applyCurrentNode"
    },
    selectedNode: {
      check : "osparc.data.model.Node",
      init : null,
      nullable : true,
      event : "changeSelectedNode"
      // apply: "_applySelectedNode"
    },
    currentTelemetry: {
      check : "Object",
      init : null,
      nullable : true,
      event : "changeCurrentTelemetry",
      // apply: "_applyCurrentTelemetry"
    }
  },

  members: {
    __diskTelemetry: null,
    __layout: null,
    __lowDiskThreshold: null,
    __diskUsage: null,
    __prevDiskUsageStateList: null,
    __testDiskUsage: null,
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

    getDiskUsage: function() {
      const lowDiskSpacePreferencesSettings = osparc.Preferences.getInstance();
      this.__lowDiskThreshold = lowDiskSpacePreferencesSettings.getLowDiskSpaceThreshold();
      const warningSize = osparc.utils.Utils.gBToBytes(this.__lowDiskThreshold); // 5 GB Default
      const criticalSize = osparc.utils.Utils.gBToBytes(0.01); // 0 GB
      let warningLevel = "NORMAL"
      if (this.__diskUsage["free"] <= criticalSize) {
        warningLevel = "CRITICAL"
      } else if (this.__diskUsage["free"] <= warningSize) {
        warningLevel = "WARNING"
      } else {
        warningLevel = "NORMAL"
      }
      return warningLevel
    },

    getDiskAvailableSpacePercent: function() {
      return this.__diskUsage ? this.__diskUsage["used_percent"] : undefined
    },

    // getNodeLabel: function(nodeId) {
    //   const nodes = this.getStudy().getWorkbench().getNodes(true);
    //   for (const node of Object.values(nodes)) {
    //     if (nodeId === node.getNodeId()) {
    //       return node.getLabel();
    //     }
    //   }
    //   return null;
    // },

    diskUsageToUI: function(id, diskUsage) {
      function isMatchingNodeId({nodeId}) {
        return nodeId === id;
      }
      function shouldDisplayMessage(prevDiskUsageState, warningLevel) {
        return prevDiskUsageState && prevDiskUsageState.nodeId === id && prevDiskUsageState.state !== warningLevel
      }

      let prevDiskUsageState = this.__prevDiskUsageStateList.find(isMatchingNodeId);

      const warningLevel = this.getDiskUsage();
      if (prevDiskUsageState === undefined) {
        this.__prevDiskUsageStateList.push({
          nodeId: id,
          state: "NORMAL"
        })
      }
      const freeSpace = osparc.utils.Utils.bytesToSize(diskUsage.free);

      const nodeName = this.getCurrentNode().getLabel();
      let message;
      let indicatorColor;

      const objIndex = this.__prevDiskUsageStateList.findIndex((obj => obj.nodeId === id));
      switch (warningLevel) {
        case "CRITICAL":
          indicatorColor = qx.theme.manager.Color.getInstance().resolve("error");
          if (shouldDisplayMessage(prevDiskUsageState, warningLevel)) {
            message = this.tr(`Out of Disk Space on "Service Filesystem" for ${nodeName}<br />The volume Service Filesystem has only ${freeSpace} disk space remaining. You can free up disk space by removing unused files in your service. Alternatively, you can run your service with a pricing plan that supports your storage requirements.`);
            osparc.FlashMessenger.getInstance().logAs(message, "ERROR");
            this.__prevDiskUsageStateList[objIndex].state = warningLevel;
          }
          break;
        case "WARNING":
          indicatorColor = qx.theme.manager.Color.getInstance().resolve("warning")
          if (shouldDisplayMessage(prevDiskUsageState, warningLevel)) {
            message = this.tr(`Low Disk Space on "Service Filesystem" for ${nodeName}<br />The volume Service Filesystem has only ${freeSpace} disk space remaining. You can free up disk space by removing unused files in your service. Alternatively, you can run your service with a pricing plan that supports your storage requirements.`);
            osparc.FlashMessenger.getInstance().logAs(message, "WARNING");
            this.__prevDiskUsageStateList[objIndex].state = warningLevel;
          }
          break;
        default:
          indicatorColor = qx.theme.manager.Color.getInstance().resolve("success");
          this.__prevDiskUsageStateList[objIndex].state = "NORMAL";
          break;
      }

      this.updateDiskIndicator(indicatorColor, freeSpace);
    },

    updateDiskIndicator: function(color, freeSpace) {
      const indicator = this.getChildControl("disk-indicator");
      const indicatorLabel = this.getChildControl("disk-indicator-label");

      const progress = `${this.getDiskAvailableSpacePercent()}%`;
      const labelDiskSize = `${freeSpace}`;
      const color1 = color || qx.theme.manager.Color.getInstance().resolve("success");
      const bgColor = qx.theme.manager.Color.getInstance().resolve("tab_navigation_bar_background_color");
      const color2 = qx.theme.manager.Color.getInstance().resolve("info");
      indicator.getContentElement().setStyles({
        "background-color": bgColor,
        "background": `linear-gradient(90deg, ${color1} ${progress}, ${color2} ${progress})`,
      });
      indicatorLabel.setValue(`${labelDiskSize} Free`);
      const isIndicatorVisible = this.getCurrentTelemetry()["node_id"] === this.getCurrentNode().getNodeId();
      indicator.setVisibility(isIndicatorVisible ? "visible" : "excluded");
      return indicator;
    },

    _applyCurrentNode: function(node) {
      const indicator = this.getChildControl("disk-indicator");
      indicator.set({
        visibility: "excluded"
      });
      osparc.workbench.DiskUsageController.getInstance().subscribe(node.getNodeId(), data => {
        if (node.getNodeId() === data["node_id"]) {
          this.__onNewUsageData(node, data);
        }
      })
    },

    __onNewUsageData: function(node, data) {
      this.setCurrentNode(node);
      this.setCurrentTelemetry(data)
      const usage = this.__diskUsage = data.usage["/"];
      // if (node.getNodeId() === data["node_id"]) {
      this.diskUsageToUI(node.getNodeId(), usage);
      // }
    }
  },

  destruct : function() {
    console.log("Exiting")
    osparc.workbench.DiskUsageController.getInstance().unsubscribe(this.getCurrentNode().getNodeId(), this.__onNewUsageData)
  }
});
