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
  extend: qx.ui.window.Window,

  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(node) {
    this.base(arguments);

    const grid = new qx.ui.layout.Grid(2, 1);
    grid.setColumnFlex(1, 1);

    this.set({
      appearance: "node-ui-cap",
      layout: grid,
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      contentPadding: this.self().CONTENT_PADDING
    });

    const captionBar = this.getChildControl("captionbar");
    captionBar.set({
      cursor: "move",
      paddingRight: 0,
      paddingLeft: this.self().PORT_DIAMETER - 6,
    });

    const menuBtn = this.__getMenuButton();
    captionBar.add(menuBtn, {
      row: 0,
      column: this.self().CAPTION_POS.MENU
    });

    const captionTitle = this.getChildControl("title");
    captionTitle.set({
      rich: true,
      cursor: "move"
    });

    this.__nodeMoving = false;

    this.setNode(node);

    this.__resetNodeUILayout();

    captionTitle.addListener("appear", () => {
      qx.event.Timer.once(() => {
        const labelDom = captionTitle.getContentElement().getDomElement();
        const maxWidth = parseInt(labelDom.style.width);
        // eslint-disable-next-line no-underscore-dangle
        const width = captionTitle.__contentSize.width;
        if (width > maxWidth) {
          this.getNode().bind("label", captionTitle, "toolTipText");
        }
      }, this, 50);
    });
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false,
      apply: "__applyNode"
    },

    type: {
      check: ["computational", "dynamic", "file", "parameter", "iterator", "probe", "unknown"],
      init: null,
      nullable: false,
      apply: "__applyType"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      apply: "__applyThumbnail"
    },
    scale: {
      check: "Number",
      event: "changeScale",
      nullable: false
    },

    isMovable: {
      check: "Boolean",
      init: true,
      nullable: false
    },
  },

  statics: {
    NODE_WIDTH: 180,
    NODE_HEIGHT: 80,
    FILE_NODE_WIDTH: 120,
    PORT_DIAMETER: 18,
    PORT_MARGIN_TOP: 4,
    CONTENT_PADDING: 2,
    PORT_CONNECTED: "@FontAwesome5Regular/dot-circle/18",
    PORT_DISCONNECTED: "@FontAwesome5Regular/circle/18",

    CAPTION_POS: {
      ICON: 0, // from qooxdoo
      TITLE: 1, // from qooxdoo
      LOCK: 2,
      MARKER: 3,
      DEPRECATED: 4,
      MENU: 5
    },

    captionHeight: function() {
      return osparc.theme.Appearance.appearances["node-ui-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["node-ui-cap/captionbar"].style().minHeight;
    },
  },

  events: {
    "renameNode": "qx.event.type.Data",
    "infoNode": "qx.event.type.Data",
    "markerClicked": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "edgeDragStart": "qx.event.type.Data",
    "edgeDragOver": "qx.event.type.Data",
    "edgeDrop": "qx.event.type.Data",
    "edgeDragEnd": "qx.event.type.Data",
    "nodeMovingStart": "qx.event.type.Event",
    "nodeMoving": "qx.event.type.Data",
    "nodeMovingStop": "qx.event.type.Event",
    "updateNodeDecorator": "qx.event.type.Event",
    "requestOpenLogger": "qx.event.type.Event",
    "highlightEdge": "qx.event.type.Data",
  },

  members: {
    __thumbnail: null,
    __svgWorkbenchCanvas: null,
    __inputLayout: null,
    __outputLayout: null,
    __optionsMenu: null,
    __markerBtn: null,
    __deleteBtn: null,
    __nodeMoving: null,

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
            column: this.self().CAPTION_POS.LOCK
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
            column: this.self().CAPTION_POS.MARKER
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
            column: this.self().CAPTION_POS.DEPRECATED
          });
          break;
        case "middle-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(2).set({
            alignY: "middle"
          })).set({
            padding: 4
          });
          this.add(control, {
            row: 0,
            column: 1
          });
          break;
        case "node-type-chip": {
          control = new osparc.ui.basic.Chip();
          let nodeType = this.getNode().getMetadata().type;
          if (this.getNode().isIterator()) {
            nodeType = "iterator";
          } else if (this.getNode().isParameter()) {
            nodeType = "parameter";
          } else if (this.getNode().isProbe()) {
            nodeType = "probe";
          }
          const type = osparc.service.Utils.getType(nodeType);
          if (type) {
            control.set({
              icon: type.icon + "13",
              toolTipText: type.label
            });
          } else if (this.getNode().isUnknown()) {
            control.set({
              icon: "@FontAwesome5Solid/question/14",
              toolTipText: "Unknown",
            });
          }
          this.getChildControl("middle-container").addAt(control, 0);
          break;
        }
        case "node-status-ui": {
          control = new osparc.ui.basic.NodeStatusUI(this.getNode()).set({
            maxHeight: 20,
            font: "text-10",
          });
          const statusLabel = control.getChildControl("label");
          const requestOpenLogger = () => this.fireEvent("requestOpenLogger");
          const evaluateLabel = () => {
            const failed = statusLabel.getValue() === "Unsuccessful";
            statusLabel.setCursor(failed ? "pointer" : "auto");
            if (control.hasListener("tap")) {
              control.removeListener("tap", requestOpenLogger);
            }
            if (failed) {
              control.addListener("tap", requestOpenLogger);
            }
          };
          evaluateLabel();
          statusLabel.addListener("changeValue", evaluateLabel);
          this.getChildControl("middle-container").addAt(control, 1);
          break;
        }
        case "progress":
          control = new qx.ui.indicator.ProgressBar().set({
            height: 10,
            margin: 4,
            decorator: "rounded",
          });
          this.add(control, {
            row: 1,
            column: 0,
            colSpan: 3
          });
          break;
        case "avatar-group":
          control = new osparc.ui.basic.AvatarGroup(20, "right").set({
            hideMyself: true,
          });
          this.getChildControl("middle-container").addAt(control, 2, {
            flex: 1
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
      this.__setNodeUIWidth(this.self().NODE_WIDTH);
      this.resetThumbnail();

      // make sure metadata is ready
      if (this.getNode().getMetadata()) {
        this.__createContentLayout();
      } else {
        this.getNode().addListenerOnce("changeMetadata", () => this.__createContentLayout(), this);
      }
    },

    __createContentLayout: function() {
      const node = this.getNode();
      if (node) {
        this.getChildControl("node-type-chip");
        this.getChildControl("node-status-ui");

        if (node.isComputational() || node.isFilePicker() || node.isIterator()) {
          this.getChildControl("progress");
        }
      }
    },

    __populateNodeLayout: function(svgWorkbenchCanvas) {
      const node = this.getNode();
      node.bind("label", this, "caption", {
        onUpdate: () => {
          setTimeout(() => this.fireEvent("updateNodeDecorator"), 50);
        }
      });
      const metadata = node.getMetadata();
      this.__createPorts(true, Boolean((metadata && metadata.inputs && Object.keys(metadata.inputs).length)));
      this.__createPorts(false, Boolean((metadata && metadata.outputs && Object.keys(metadata.outputs).length)));
      if (node.isComputational() || node.isFilePicker()) {
        node.getStatus().bind("progress", this.getChildControl("progress"), "value", {
          converter: val => val === null ? 0 : val
        });
      }
      if (node.isComputational()) {
        this.setType("computational");
      } else if (node.isDynamic()) {
        this.setType("dynamic");
      } else if (node.isFilePicker()) {
        this.setType("file");
      } else if (node.isParameter()) {
        this.setType("parameter");
      } else if (node.isIterator()) {
        this.__svgWorkbenchCanvas = svgWorkbenchCanvas;
        this.setType("iterator");
      } else if (node.isProbe()) {
        this.setType("probe");
      } else if (node.isUnknown()) {
        this.setType("unknown");
      }
      this.addListener("resize", () => {
        setTimeout(() => this.fireEvent("updateNodeDecorator"), 50);
      });

      if (node.getPropsForm()) {
        node.getPropsForm().addListener("highlightEdge", e => this.fireDataEvent("highlightEdge", e.getData()), this);
      }
    },

    populateNodeLayout: function(svgWorkbenchCanvas) {
      if (this.getNode().getMetadata()) {
        this.__populateNodeLayout(svgWorkbenchCanvas);
      } else {
        this.getNode().addListenerOnce("changeMetadata", () => this.__populateNodeLayout(svgWorkbenchCanvas), this);
      }
    },

    __applyNode: function(node) {
      node.addListener("changePosition", e => {
        this.moveNodeTo(e.getData());
        this.fireEvent("nodeMovingStop");
      });

      if (node.isDynamic()) {
        const startButton = new qx.ui.menu.Button().set({
          label: this.tr("Start"),
          icon: "@FontAwesome5Solid/play/10"
        });
        node.attachHandlersToStartButton(startButton);
        this.__optionsMenu.addAt(startButton, 0);

        const stopButton = new qx.ui.menu.Button().set({
          label: this.tr("Stop"),
          icon: "@FontAwesome5Solid/stop/10"
        });
        node.attachHandlersToStopButton(stopButton);
        this.__optionsMenu.addAt(stopButton, 1);
      }

      if (node.getKey().includes("parameter/int")) {
        const makeIterator = new qx.ui.menu.Button().set({
          label: this.tr("Convert to Iterator"),
          icon: "@FontAwesome5Solid/sync-alt/10"
        });
        makeIterator.addListener("execute", () => node.convertToIterator("int"), this);
        this.__optionsMenu.add(makeIterator);
      } else if (node.getKey().includes("data-iterator/int-range")) {
        const convertToParameter = new qx.ui.menu.Button().set({
          label: this.tr("Convert to Parameter"),
          icon: "@FontAwesome5Solid/sync-alt/10"
        });
        convertToParameter.addListener("execute", () => node.convertToParameter("int"), this);
        this.__optionsMenu.add(convertToParameter);
      }

      const lockState = node.getStatus().getLockState();
      const lock = this.getChildControl("lock");
      lockState.bind("locked", lock, "visibility", {
        converter: locked => {
          if (locked) {
            if (node.isDynamic()) {
              // if it's dynamic, don't show the lock if it's me using it
              const myGroupId = osparc.auth.Data.getInstance().getGroupId();
              const currentUserGroupIds = lockState.getCurrentUserGroupIds();
              return currentUserGroupIds.includes(myGroupId) ? "excluded" : "visible";
            } else {
              return "visible";
            }
          }
          return "excluded";
        }
      });

      const updateUserGroupIds = () => {
        const currentUserGroupIds = lockState.getCurrentUserGroupIds();
        const avatarGroup = this.getChildControl("avatar-group");
        avatarGroup.setUserGroupIds(currentUserGroupIds);
        avatarGroup.setVisibility(currentUserGroupIds.length ? "visible" : "excluded");
      };
      updateUserGroupIds();
      lockState.addListener("changeCurrentUserGroupIds", updateUserGroupIds);

      this.__markerBtn.show();
      this.getNode().bind("marker", this.__markerBtn, "label", {
        converter: val => val ? this.tr("Remove Marker") : this.tr("Add Marker")
      });
      this.__markerBtn.addListener("execute", () => node.toggleMarker());

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

      // do not allow modifying the pipeline
      node.getStudy().bind("pipelineRunning", this.__deleteBtn, "enabled", {
        converter: running => !running
      });

      const evaluateLifeCycleIcon = () => {
        const deprecatedIcon = this.getChildControl("deprecated-icon");
        deprecatedIcon.exclude();
        if (node.isDeprecated()) {
          deprecatedIcon.show();
          deprecatedIcon.set({
            textColor: osparc.service.StatusUI.getColor("deprecated")
          });
          let ttMsg = osparc.service.Utils.DEPRECATED_SERVICE_TEXT;
          const deprecatedDateMsg = osparc.service.Utils.getDeprecationDateText(node.getMetadata());
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
        case "unknown":
          this.__turnIntoUnknownUI();
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
      const width = this.self().FILE_NODE_WIDTH;
      this.__setNodeUIWidth(width);

      const middleContainer = this.getChildControl("middle-container");
      middleContainer.exclude();

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
      const width = 120;
      this.__setNodeUIWidth(width);

      const valueLabel = new qx.ui.basic.Label().set({
        paddingLeft: 4,
        font: "text-14"
      });
      const outputToValue = outputs => {
          if ("out_1" in outputs && "value" in outputs["out_1"]) {
            const val = outputs["out_1"]["value"];
            if (Array.isArray(val)) {
              return "[" + val.join(",") + "]";
            }
            return String(val);
          }
          return "";
      }
      this.getNode().bind("outputs", valueLabel, "value", {
        converter: outputs => outputToValue(outputs)
      });
      this.getNode().bind("outputs", valueLabel, "toolTipText", {
        converter: outputs => outputToValue(outputs)
      });
      const middleContainer = this.getChildControl("middle-container");
      middleContainer.add(valueLabel, {
        flex: 1
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
      const width = 120;
      this.__setNodeUIWidth(width);

      const linkLabel = new osparc.ui.basic.LinkLabel().set({
        paddingLeft: 4,
        font: "text-14",
        rich: false, // this will make the ellipsis work
      });
      const middleContainer = this.getChildControl("middle-container");
      middleContainer.add(linkLabel, {
        flex: 1
      });

      this.getNode().getPropsForm().addListener("linkFieldModified", () => this.__setProbeValue(linkLabel), this);
      this.__setProbeValue(linkLabel);
    },

    __turnIntoUnknownUI: function() {
      const width = 110;
      this.__setNodeUIWidth(width);

      this.setEnabled(false);

      this.fireEvent("updateNodeDecorator");
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

    __setProbeValue: function(linkLabel) {
      const populateLinkLabel = linkInfo => {
        const download = true;
        const locationId = linkInfo.store;
        const fileId = linkInfo.path;
        osparc.store.Data.getInstance().getPresignedLink(download, locationId, fileId)
          .then(presignedLinkData => {
            if ("resp" in presignedLinkData && presignedLinkData.resp) {
              const filename = linkInfo.filename || osparc.file.FilePicker.getFilenameFromPath(linkInfo);
              linkLabel.set({
                value: filename,
                url: presignedLinkData.resp.link
              });
            }
          });
      }

      const link = this.getNode().getLink("in_1");
      if (link && "nodeUuid" in link) {
        const inputNodeId = link["nodeUuid"];
        const portKey = link["output"];
        const inputNode = this.getNode().getWorkbench().getNode(inputNodeId);
        if (inputNode) {
          inputNode.bind("outputs", linkLabel, "value", {
            converter: outputs => {
              if (portKey in outputs && "value" in outputs[portKey] && outputs[portKey]["value"]) {
                const val = outputs[portKey]["value"];
                if (this.getNode().getMetadata()["key"].includes("probe/array")) {
                  return "[" + val.join(",") + "]";
                } else if (this.getNode().getMetadata()["key"].includes("probe/file")) {
                  const filename = val.filename || osparc.file.FilePicker.getFilenameFromPath(val);
                  populateLinkLabel(val);
                  return filename;
                }
                return String(val);
              }
              return "";
            }
          });
        }
      } else {
        linkLabel.setValue("");
      }
    },

    __createPorts: function(isInput, draw) {
      if (draw === false) {
        this.__createPort(isInput, true);
        return;
      }
      const port = this.__createPort(isInput);
      port.addListener("mouseover", () => {
        port.setSource(this.self().PORT_CONNECTED);
      }, this);
      port.addListener("mouseout", () => {
        const isConnected = isInput ? this.getNode().getInputConnected() : this.getNode().getOutputConnected();
        port.set({
          source: isConnected ? this.self().PORT_CONNECTED : this.self().PORT_DISCONNECTED
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
          converter: isConnected => isConnected ? this.self().PORT_CONNECTED : this.self().PORT_DISCONNECTED
        });
      } else {
        this.getNode().getStatus().bind("output", port, "textColor", {
          converter: output => osparc.service.StatusUI.getColor(output)
        });
        this.getNode().bind("outputConnected", port, "source", {
          converter: isConnected => isConnected ? this.self().PORT_CONNECTED : this.self().PORT_DISCONNECTED
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

    moveNodeTo: function(pos) {
      this.moveTo(pos.x, pos.y);
    },

    setPosition: function(pos) {
      const node = this.getNode();
      node.setPosition(pos);
      this.moveNodeTo(pos);
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
      this.setPosition({
        x: snapX,
        y: snapY
      });
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

    __getMenuButton: function() {
      const optionsMenu = this.__optionsMenu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const renameBtn = new qx.ui.menu.Button().set({
        label: this.tr("Rename"),
        icon: "@FontAwesome5Solid/i-cursor/10"
      });
      renameBtn.getChildControl("shortcut").setValue("F2");
      renameBtn.addListener("execute", () => this.fireDataEvent("renameNode", this.getNodeId()));
      optionsMenu.add(renameBtn);

      const markerBtn = this.__markerBtn = new qx.ui.menu.Button().set({
        icon: "@FontAwesome5Solid/bookmark/10",
        visibility: "excluded"
      });
      optionsMenu.add(markerBtn);

      const infoBtn = new qx.ui.menu.Button().set({
        label: this.tr("Information..."),
        icon: "@FontAwesome5Solid/info/10"
      });
      infoBtn.getChildControl("shortcut").setValue("I");
      infoBtn.addListener("execute", () => this.fireDataEvent("infoNode", this.getNodeId()));
      optionsMenu.add(infoBtn);

      const deleteBtn = this.__deleteBtn = new qx.ui.menu.Button().set({
        label: this.tr("Delete"),
        icon: "@FontAwesome5Solid/trash/10"
      });
      deleteBtn.getChildControl("shortcut").setValue("Del");
      deleteBtn.addListener("execute", () => this.fireDataEvent("removeNode", this.getNodeId()));
      optionsMenu.add(deleteBtn);

      const menuBtn = new qx.ui.form.MenuButton().set({
        menu: optionsMenu,
        icon: "@FontAwesome5Solid/ellipsis-v/9",
        height: 18,
        width: 18,
        allowGrowX: false,
        allowGrowY: false
      });
      return menuBtn;
    },

    getInputPort: function() {
      return this.__inputLayout;
    },

    getOutputPort: function() {
      return this.__outputLayout;
    },

    __createPort: function(isInput, placeholder = false) {
      let port = null;
      const width = this.self().PORT_DIAMETER;
      if (placeholder) {
        port = new qx.ui.core.Spacer(width, width);
      } else {
        port = new qx.ui.basic.Image().set({
          source: this.self().PORT_DISCONNECTED, // disconnected by default
          height: width,
          width: width,
          marginTop: this.self().PORT_MARGIN_TOP,
          draggable: true,
          droppable: true,
          alignY: "top",
          backgroundColor: "background-main"
        });
        port.setCursor("pointer");
        port.getContentElement().setStyles({
          "border-radius": width+"px"
        });
        port.isInput = isInput;
      }
      // make the ports exit the NodeUI
      port.set({
        marginLeft: isInput ? (-10 + this.self().CONTENT_PADDING) : 0,
        marginRight: isInput ? 0 : (-10 - this.self().CONTENT_PADDING)
      });

      this.add(port, {
        row: 0,
        column: isInput ? 0 : 2
      });

      if (isInput) {
        this.__inputLayout = port;
      } else {
        this.__outputLayout = port;
      }

      return port;
    },

    getEdgePoint: function(port) {
      const bounds = this.getCurrentBounds();
      const captionHeight = Math.max(this.getChildControl("captionbar").getSizeHint().height, this.self().captionHeight());
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width - 1;
      const y = bounds.top + captionHeight + this.self().PORT_DIAMETER/2 + this.self().PORT_MARGIN_TOP + 2;
      return [x, y];
    },

    getCurrentBounds: function() {
      let bounds = this.getBounds();
      let cel = this.getContentElement();
      if (cel) {
        let domeEle = cel.getDomElement();
        if (domeEle) {
          bounds.left = parseInt(domeEle.style.left);
          bounds.top = parseInt(domeEle.style.top);
        }
      }
      return bounds;
    },

    __scaleCoordinates: function(x, y) {
      return {
        x: parseInt(x / this.getScale()),
        y: parseInt(y / this.getScale())
      };
    },

    __setPositionFromEvent: function(e) {
      // this.__dragRange is defined in qx.ui.core.MMovable
      const sideBarWidth = this.__dragRange.left;
      const navigationBarHeight = this.__dragRange.top;
      const native = e.getNativeEvent();
      const x = native.clientX + this.__dragLeft - sideBarWidth;
      const y = native.clientY + this.__dragTop - navigationBarHeight;
      const coords = this.__scaleCoordinates(x, y);
      const insets = this.getLayoutParent().getInsets();
      this.setDomPosition(coords.x - (insets.left || 0), coords.y - (insets.top || 0));
      return coords;
    },

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move") || !this.getIsMovable()) {
        return;
      }
      const coords = this.__setPositionFromEvent(e);
      e.stopPropagation();
      if (this.__nodeMoving === false) {
        this.__nodeMoving = true;
        this.fireEvent("nodeMovingStart");
      }
      this.fireDataEvent("nodeMoving", coords);
    },

    // override qx.ui.core.MMovable
    _onMovePointerUp : function(e) {
      if (this.hasListener("roll")) {
        this.removeListener("roll", this._onMoveRoll, this);
      }

      // Only react when dragging is active
      if (!this.hasState("move") || !this.getIsMovable()) {
        return;
      }

      this._onMovePointerMove(e);

      this.__nodeMoving = false;

      // Only consolidate position when it stops moving
      const coords = this.__setPositionFromEvent(e);
      this.getNode().setPosition(coords);

      this.fireEvent("nodeMovingStop");

      // Remove drag state
      this.removeState("move");

      this.releaseCapture();

      e.stopPropagation();
    },
  }
});
