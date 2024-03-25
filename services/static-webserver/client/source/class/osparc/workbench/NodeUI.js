/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Window that is used to represent a node in the WorkbenchUI.
 *
 * It implements Drag&Drop mechanism to provide internode connections.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeUI = new osparc.workbench.NodeUI(node);
 *   nodeUI.populateNodeLayout();
 *   workbench.add(nodeUI)
 * </pre>
 */

qx.Class.define("osparc.workbench.NodeUI", {
  extend: osparc.workbench.BaseNodeUI,

  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(node) {
    this.base(arguments);

    this.setNode(node);

    this.__resetNodeUILayout();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false,
      apply: "__applyNode"
    },

    type: {
      check: ["normal", "file", "parameter", "iterator", "probe"],
      init: "normal",
      nullable: false,
      apply: "__applyType"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      apply: "__applyThumbnail"
    }
  },

  statics: {
    NODE_WIDTH: 180,
    NODE_HEIGHT: 80
  },

  events: {
    "updateNodeDecorator": "qx.event.type.Event"
  },

  members: {
    __thumbnail: null,
    __svgWorkbenchCanvas: null,

    getNodeType: function() {
      return "service";
    },

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "lock":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/lock/12",
            padding: 4,
            visibility: "excluded"
          });
          this.getChildControl("captionbar").add(control, {
            row: 0,
            column: osparc.workbench.BaseNodeUI.CAPTION_POS.LOCK
          });
          break;
        case "marker":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/bookmark/12",
            padding: 4,
            visibility: "excluded"
          });
          this.getChildControl("captionbar").add(control, {
            row: 0,
            column: osparc.workbench.BaseNodeUI.CAPTION_POS.MARKER
          });
          control.addListener("tap", () => this.fireDataEvent("markerClicked", this.getNode().getNodeId()));
          break;
        case "deprecated-icon":
          control = new qx.ui.basic.Image().set({
            source: "@MaterialIcons/update/14",
            padding: 4
          });
          this.getChildControl("captionbar").add(control, {
            row: 0,
            column: osparc.workbench.BaseNodeUI.CAPTION_POS.DEPRECATED
          });
          break;
        case "chips": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(3, 3).set({
            alignY: "middle"
          })).set({
            margin: [3, 4]
          });
          let nodeType = this.getNode().getMetaData().type;
          if (this.getNode().isIterator()) {
            nodeType = "iterator";
          } else if (this.getNode().isProbe()) {
            nodeType = "probe";
          }
          const type = osparc.service.Utils.getType(nodeType);
          if (type) {
            const chip = new osparc.ui.basic.Chip().set({
              icon: type.icon + "14",
              toolTipText: type.label
            });
            control.add(chip);
          }
          const nodeStatus = new osparc.ui.basic.NodeStatusUI(this.getNode());
          control.add(nodeStatus);
          this.add(control, {
            row: 0,
            column: 1
          });
          break;
        }
        case "progress":
          control = new qx.ui.indicator.ProgressBar().set({
            height: 10,
            margin: 4
          });
          this.add(control, {
            row: 1,
            column: 0,
            colSpan: 3
          });
          break;
        case "usage-indicator":
          control = new osparc.workbench.DiskUsageIndicator();
          this.add(control, {
            row: 2,
            column: 0,
            colSpan: 4
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __resetNodeUILayout: function() {
      this.set({
        width: this.self(arguments).NODE_WIDTH,
        maxWidth: this.self(arguments).NODE_WIDTH,
        minWidth: this.self(arguments).NODE_WIDTH
      });
      this.resetThumbnail();

      this.__createWindowLayout();
    },

    __createWindowLayout: function() {
      const node = this.getNode();
      if (node.getThumbnail()) {
        this.setThumbnail(node.getThumbnail());
      }

      this.getChildControl("chips").show();

      if (node.isComputational() || node.isFilePicker() || node.isIterator()) {
        this.getChildControl("progress").show();
      }
    },

    populateNodeLayout: function(svgWorkbenchCanvas) {
      const node = this.getNode();
      node.bind("label", this, "caption", {
        onUpdate: () => {
          setTimeout(() => this.fireEvent("updateNodeDecorator"), 50);
        }
      });
      const metaData = node.getMetaData();
      this.__createPorts(true, Boolean((metaData && metaData.inputs && Object.keys(metaData.inputs).length)));
      this.__createPorts(false, Boolean((metaData && metaData.outputs && Object.keys(metaData.outputs).length)));
      if (node.isComputational() || node.isFilePicker()) {
        node.getStatus().bind("progress", this.getChildControl("progress"), "value", {
          converter: val => val === null ? 0 : val
        });
      }
      if (node.isFilePicker()) {
        this.setType("file");
      } else if (node.isParameter()) {
        this.setType("parameter");
      } else if (node.isIterator()) {
        this.__svgWorkbenchCanvas = svgWorkbenchCanvas;
        this.setType("iterator");
      } else if (node.isProbe()) {
        this.setType("probe");
      }
    },

    __applyNode: function(node) {
      if (node.isDynamic()) {
        const startButton = new qx.ui.menu.Button().set({
          label: this.tr("Start"),
          icon: "@FontAwesome5Solid/play/10"
        });
        node.attachHandlersToStartButton(startButton);
        this._optionsMenu.addAt(startButton, 0);

        const stopButton = new qx.ui.menu.Button().set({
          label: this.tr("Stop"),
          icon: "@FontAwesome5Solid/stop/10"
        });
        node.attachVisibilityHandlerToStopButton(stopButton);
        node.attachExecuteHandlerToStopButton(stopButton);
        this._optionsMenu.addAt(stopButton, 1);
      }

      if (node.getKey().includes("parameter/int")) {
        const makeIterator = new qx.ui.menu.Button().set({
          label: this.tr("Convert to Iterator"),
          icon: "@FontAwesome5Solid/sync-alt/10"
        });
        makeIterator.addListener("execute", () => node.convertToIterator("int"), this);
        this._optionsMenu.add(makeIterator);
      } else if (node.getKey().includes("data-iterator/int-range")) {
        const convertToParameter = new qx.ui.menu.Button().set({
          label: this.tr("Convert to Parameter"),
          icon: "@FontAwesome5Solid/sync-alt/10"
        });
        convertToParameter.addListener("execute", () => node.convertToParameter("int"), this);
        this._optionsMenu.add(convertToParameter);
      }

      const lock = this.getChildControl("lock");
      if (node.getPropsForm()) {
        node.getPropsForm().bind("enabled", lock, "visibility", {
          converter: val => val ? "excluded" : "visible"
        });
      }
      this._markerBtn.show();
      this.getNode().bind("marker", this._markerBtn, "label", {
        converter: val => val ? this.tr("Remove Marker") : this.tr("Add Marker")
      });
      this._markerBtn.addListener("execute", () => this.getNode().toggleMarker());

      const marker = this.getChildControl("marker");
      const updateMarker = () => {
        node.bind("marker", marker, "visibility", {
          converter: val => val ? "visible" : "excluded"
        });
        if (node.getMarker()) {
          node.getMarker().bind("color", marker, "textColor");
        }
      };
      node.addListener("changeMarker", () => updateMarker());
      updateMarker();

      const evaluateLifeCycleIcon = () => {
        const deprecatedIcon = this.getChildControl("deprecated-icon");
        deprecatedIcon.exclude();
        if (node.isDeprecated()) {
          deprecatedIcon.show();
          deprecatedIcon.set({
            textColor: osparc.service.StatusUI.getColor("deprecated")
          });
          let ttMsg = osparc.service.Utils.DEPRECATED_SERVICE_TEXT;
          const deprecatedDateMsg = osparc.service.Utils.getDeprecationDateText(node.getMetaData());
          if (deprecatedDateMsg) {
            ttMsg = ttMsg + "<br>" + deprecatedDateMsg;
          }
          const deprecatedTTMsg = node.isDynamic() ? osparc.service.Utils.DEPRECATED_DYNAMIC_INSTRUCTIONS : osparc.service.Utils.DEPRECATED_COMPUTATIONAL_INSTRUCTIONS;
          if (deprecatedTTMsg) {
            ttMsg = ttMsg + "<br>" + deprecatedTTMsg;
          }
          const toolTip = new qx.ui.tooltip.ToolTip().set({
            label: ttMsg,
            icon: osparc.service.StatusUI.getIconSource("deprecated"),
            rich: true,
            maxWidth: 250
          });
          deprecatedIcon.setToolTip(toolTip);
        } else if (node.isRetired()) {
          deprecatedIcon.show();
          deprecatedIcon.set({
            textColor: osparc.service.StatusUI.getColor("retired")
          });

          let ttMsg = osparc.service.Utils.RETIRED_SERVICE_TEXT;
          const deprecatedTTMsg = node.isDynamic() ? osparc.service.Utils.RETIRED_DYNAMIC_INSTRUCTIONS : osparc.service.Utils.RETIRED_COMPUTATIONAL_INSTRUCTIONS;
          if (deprecatedTTMsg) {
            ttMsg = ttMsg + "<br>" + deprecatedTTMsg;
          }
          const toolTip = new qx.ui.tooltip.ToolTip().set({
            label: ttMsg,
            icon: osparc.service.StatusUI.getIconSource("retired"),
            rich: true,
            maxWidth: 250
          });
          deprecatedIcon.setToolTip(toolTip);
        }
      };
      evaluateLifeCycleIcon();
      this.getNode().addListener("changeVersion", () => evaluateLifeCycleIcon());
      const indicator = this.getChildControl("usage-indicator");
      indicator.setCurrentNode(node);
    },

    __applyType: function(type) {
      switch (type) {
        case "file":
          this.__checkTurnIntoFileUI();
          this.getNode().addListener("changeOutputs", () => this.__checkTurnIntoFileUI(), this);
          break;
        case "parameter":
          this.__turnIntoParameterUI();
          break;
        case "iterator":
          this.__checkTurnIntoIteratorUI();
          this.getNode().addListener("changeOutputs", () => this.__checkTurnIntoIteratorUI(), this);
          break;
        case "probe":
          this.__turnIntoProbeUI();
          break;
      }
    },

    __setNodeUIWidth: function(width) {
      this.set({
        width: width,
        maxWidth: width,
        minWidth: width,
        minHeight: 60
      });
    },

    __checkTurnIntoFileUI: function() {
      const outputs = this.getNode().getOutputs();
      if ([null, ""].includes(osparc.file.FilePicker.getOutput(outputs))) {
        this.__resetNodeUILayout();
      } else {
        this.__turnIntoFileUI();
      }
    },

    __turnIntoFileUI: function() {
      const width = 120;
      this.__setNodeUIWidth(width);

      const chipContainer = this.getChildControl("chips");
      chipContainer.exclude();

      if (this.hasChildControl("progress")) {
        this.getChildControl("progress").exclude();
      }

      const title = this.getChildControl("title");
      title.set({
        // maxHeight: 28, // two lines in Roboto
        maxHeight: 34, // two lines in Manrope
        maxWidth: 90
      });

      const outputs = this.getNode().getOutputs();
      let imageSrc = null;
      if (osparc.file.FilePicker.isOutputFromStore(outputs)) {
        imageSrc = "@FontAwesome5Solid/file-alt/34";
      } else if (osparc.file.FilePicker.isOutputDownloadLink(outputs)) {
        imageSrc = "@FontAwesome5Solid/link/34";
      }
      if (imageSrc) {
        this.setThumbnail(imageSrc);
      }
      this.fireEvent("updateNodeDecorator");
    },

    __turnIntoParameterUI: function() {
      const width = 100;
      this.__setNodeUIWidth(width);

      const label = new qx.ui.basic.Label().set({
        font: "text-18"
      });
      const chipContainer = this.getChildControl("chips");
      chipContainer.add(label);

      this.getNode().bind("outputs", label, "value", {
        converter: outputs => {
          if ("out_1" in outputs && "value" in outputs["out_1"]) {
            const val = outputs["out_1"]["value"];
            if (Array.isArray(val)) {
              return "[" + val.join(",") + "]";
            }
            return String(val);
          }
          return "";
        }
      });
      this.fireEvent("updateNodeDecorator");
    },

    __turnIntoIteratorUI: function() {
      const width = 150;
      const height = 69;
      this.__setNodeUIWidth(width);

      // add shadows
      if (this.__svgWorkbenchCanvas) {
        const nShadows = 2;
        this.shadows = [];
        for (let i=0; i<nShadows; i++) {
          const nodeUIShadow = this.__svgWorkbenchCanvas.drawNodeUI(width, height);
          this.shadows.push(nodeUIShadow);
        }
      }
    },

    __turnIntoIteratorIteratedUI: function() {
      this.removeShadows;
      this.__turnIntoParameterUI();
      if (this.hasChildControl("progress")) {
        this.getChildControl("progress").exclude();
      }
      this.getNode().getPropsForm().setEnabled(false);
    },

    __turnIntoProbeUI: function() {
      const width = 150;
      this.__setNodeUIWidth(width);

      const label = new qx.ui.basic.Label().set({
        paddingLeft: 5,
        font: "text-18"
      });
      const chipContainer = this.getChildControl("chips");
      chipContainer.add(label);

      this.getNode().getPropsForm().addListener("linkFieldModified", () => this.__setProbeValue(label), this);
      this.__setProbeValue(label);
    },

    __checkTurnIntoIteratorUI: function() {
      const outputs = this.getNode().getOutputs();
      const portKey = "out_1";
      if (portKey in outputs && "value" in outputs[portKey]) {
        this.__turnIntoIteratorIteratedUI();
      } else {
        this.__turnIntoIteratorUI();
      }
    },

    removeShadows: function() {
      if (this.__svgWorkbenchCanvas && "shadows" in this) {
        this.shadows.forEach(shadow => {
          osparc.wrapper.Svg.removeItem(shadow);
        });
        delete this["shadows"];
      }
    },

    __setProbeValue: function(label) {
      const link = this.getNode().getLink("in_1");
      if (link && "nodeUuid" in link) {
        const inputNodeId = link["nodeUuid"];
        const portKey = link["output"];
        const inputNode = this.getNode().getWorkbench().getNode(inputNodeId);
        if (inputNode) {
          inputNode.bind("outputs", label, "value", {
            converter: outputs => {
              if (portKey in outputs && "value" in outputs[portKey]) {
                const val = outputs[portKey]["value"];
                if (Array.isArray(val)) {
                  return "[" + val.join(",") + "]";
                }
                return String(val);
              }
              return "";
            }
          });
        }
      } else {
        label.setValue("");
      }
    },

    __createPorts: function(isInput, draw) {
      if (draw === false) {
        this._createPort(isInput, true);
        return;
      }
      const port = this._createPort(isInput);
      port.addListener("mouseover", () => {
        port.setSource(osparc.workbench.BaseNodeUI.PORT_CONNECTED);
      }, this);
      port.addListener("mouseout", () => {
        const isConnected = isInput ? this.getNode().getInputConnected() : this.getNode().getOutputConnected();
        port.set({
          source: isConnected ? osparc.workbench.BaseNodeUI.PORT_CONNECTED : osparc.workbench.BaseNodeUI.PORT_DISCONNECTED
        });
      }, this);
      if (isInput) {
        this.getNode().getStatus().bind("dependencies", port, "textColor", {
          converter: dependencies => {
            if (dependencies !== null) {
              return osparc.service.StatusUI.getColor(dependencies.length ? "modified" : "ready");
            }
            return osparc.service.StatusUI.getColor();
          }
        });
        this.getNode().bind("inputConnected", port, "source", {
          converter: isConnected => isConnected ? osparc.workbench.BaseNodeUI.PORT_CONNECTED : osparc.workbench.BaseNodeUI.PORT_DISCONNECTED
        });
      } else {
        this.getNode().getStatus().bind("output", port, "textColor", {
          converter: output => osparc.service.StatusUI.getColor(output)
        });
        this.getNode().bind("outputConnected", port, "source", {
          converter: isConnected => isConnected ? osparc.workbench.BaseNodeUI.PORT_CONNECTED : osparc.workbench.BaseNodeUI.PORT_DISCONNECTED
        });
      }

      this.__addDragDropMechanism(port, isInput);
    },

    __addDragDropMechanism: function(port, isInput) {
      [
        ["dragstart", "edgeDragStart"],
        ["dragover", "edgeDragOver"],
        ["drop", "edgeDrop"],
        ["dragend", "edgeDragEnd"]
      ].forEach(eventPair => {
        port.addListener(eventPair[0], e => {
          const eData = this.__createDragDropEventData(e, isInput);
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    __createDragDropEventData: function(e, isInput) {
      return {
        event: e,
        nodeId: this.getNodeId(),
        isInput: isInput
      };
    },

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }
      const coords = this._setPositionFromEvent(e);
      this.getNode().setPosition(coords);
      this.base(arguments, e);
    },

    setPosition: function(pos) {
      const node = this.getNode();
      node.setPosition(pos);
      this.moveTo(node.getPosition().x, node.getPosition().y);
    },

    snapToGrid: function() {
      const node = this.getNode();
      const {
        x,
        y
      } = node.getPosition();
      const snapGrid = 20;
      const snapX = Math.round(x/snapGrid)*snapGrid;
      const snapY = Math.round(y/snapGrid)*snapGrid;
      node.setPosition({
        x: snapX,
        y: snapY
      });
      this.moveTo(node.getPosition().x, node.getPosition().y);
    },

    __applyThumbnail: function(thumbnailSrc) {
      if (this.__thumbnail) {
        this.remove(this.__thumbnail);
        this.__thumbnail = null;
      }
      if (thumbnailSrc) {
        if (osparc.utils.Utils.isUrl(thumbnailSrc)) {
          this.__thumbnail = new qx.ui.basic.Image(thumbnailSrc).set({
            height: 100,
            allowShrinkX: true,
            scale: true
          });
        } else {
          this.__thumbnail = new osparc.ui.basic.Thumbnail(thumbnailSrc).set({
            padding: 12
          });
        }
        this.add(this.__thumbnail, {
          row: 0,
          column: 1
        });
      }
    },

    __filterText: function(text) {
      const label = this.getNode().getLabel()
        .trim()
        .toLowerCase();
      if (label.indexOf(text) === -1) {
        return true;
      }
      return false;
    },

    __filterTags: function(tags) {
      if (tags && tags.length) {
        const category = this.getNode().getMetaData().category || "";
        const type = this.getNode().getMetaData().type || "";
        if (!tags.includes(osparc.utils.Utils.capitalize(category.trim())) && !tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    // implement osparc.filter.IFilterable
    _shouldApplyFilter: function(data) {
      if (data.text) {
        return this.__filterText(data.text);
      }
      if (data.tags && data.tags.length) {
        return this.__filterTags(data.tags);
      }
      return false;
    }
  }
});
