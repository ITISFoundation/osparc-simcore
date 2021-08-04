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
 *   let nodeUI = new osparc.component.workbench.NodeUI(node);
 *   nodeUI.populateNodeLayout();
 *   workbench.add(nodeUI)
 * </pre>
 */

qx.Class.define("osparc.component.workbench.NodeUI", {
  extend: qx.ui.window.Window,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,

  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(node) {
    this.base();

    const grid = new qx.ui.layout.Grid(3, 1);
    grid.setColumnFlex(0, 1);

    this.set({
      layout: grid,
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      width: this.self(arguments).NODE_WIDTH,
      maxWidth: this.self(arguments).NODE_WIDTH,
      minWidth: this.self(arguments).NODE_WIDTH,
      contentPadding: 0
    });

    this.setNode(node);

    this.__createNodeLayout();

    this.subscribeToFilterGroup("workbench");

    this.getChildControl("captionbar").setCursor("move");
    this.getChildControl("title").setCursor("move");
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    scale: {
      check: "Number",
      event: "changeScale",
      nullable: false
    },

    thumbnail: {
      check: "String",
      nullable: true,
      apply: "_applyThumbnail"
    },

    appearance: {
      init: "window-small-cap",
      refine: true
    }
  },

  events: {
    "edgeDragStart": "qx.event.type.Data",
    "edgeDragOver": "qx.event.type.Data",
    "edgeDrop": "qx.event.type.Data",
    "edgeDragEnd": "qx.event.type.Data",
    "nodeMoving": "qx.event.type.Event",
    "nodeStoppedMoving": "qx.event.type.Event"
  },

  statics: {
    NODE_WIDTH: 200,
    NODE_HEIGHT: 80,
    PORT_HEIGHT: 16,
    captionHeight: function() {
      return osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().minHeight;
    }
  },

  members: {
    __inputOutputLayout: null,
    __inputLayout: null,
    __outputLayout: null,
    __progressBar: null,
    __thumbnail: null,

    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "inputOutput":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          control.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          this.add(control, {
            row: 0,
            column: 0
          });
          break;
        case "chips": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(3, 3)).set({
            margin: [3, 4]
          });
          const nodeType = this.getNode().isContainer() ? "container" : this.getNode().getMetaData().type;
          const type = osparc.utils.Services.getType(nodeType);
          if (type) {
            control.add(new osparc.ui.basic.Chip(type.label, type.icon + "12"));
          }
          this.add(control, {
            row: 1,
            column: 0
          });
          break;
        }
        case "progress":
          control = new qx.ui.indicator.ProgressBar().set({
            height: 10,
            margin: 4
          });
          this.add(control, {
            row: 2,
            column: 0
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __createNodeLayout: function() {
      const node = this.getNode();
      if (node.getThumbnail()) {
        this.setThumbnail(node.getThumbnail());
      }
      this.__inputOutputLayout = this.getChildControl("inputOutput");
      const chipContainer = this.getChildControl("chips");
      if (node.isComputational() || node.isFilePicker()) {
        this.__progressBar = this.getChildControl("progress");
      }

      const nodeStatus = new osparc.ui.basic.NodeStatusUI(node);
      chipContainer.add(nodeStatus);
    },

    populateNodeLayout: function() {
      const node = this.getNode();
      node.bind("label", this, "caption");
      if (node.isContainer()) {
        this.setIcon("@FontAwesome5Solid/folder-open/14");
      }
      const metaData = node.getMetaData();
      this.__createUIPorts(true, metaData && metaData.inputs);
      this.__createUIPorts(false, metaData && metaData.outputs);
      if (node.isComputational() || node.isFilePicker()) {
        node.getStatus().bind("progress", this.__progressBar, "value");
      }
      /*
      node.getStatus().bind("running", this, "decorator", {
        // Paint borders
        converter: state => osparc.utils.StatusUI.getBorderDecorator(state)
      });
      */
      if (node.isFilePicker()) {
        this.turnIntoFileUI();
      }
    },

    turnIntoFileUI: function() {
      const outputs = this.getNode().getOutputs();
      if ([null, ""].includes(osparc.file.FilePicker.getOutput(outputs))) {
        return;
      }

      const fileUIWidth = 120;
      this.set({
        width: fileUIWidth,
        maxWidth: fileUIWidth,
        minWidth: fileUIWidth
      });

      // two lines
      this.getChildControl("title").set({
        rich: true,
        wrap: true,
        maxHeight: 28,
        minWidth: fileUIWidth-16,
        maxWidth: fileUIWidth-16
      });

      const chipContainer = this.getChildControl("chips");
      chipContainer.exclude();

      if (this.__progressBar) {
        this.__progressBar.exclude();
      }

      let imageSrc = null;
      if (osparc.file.FilePicker.isOutputFromStore(outputs)) {
        imageSrc = "@FontAwesome5Solid/file-alt/34";
      }
      if (osparc.file.FilePicker.isOutputDownloadLink(outputs)) {
        imageSrc = "@FontAwesome5Solid/link/34";
      }
      if (imageSrc) {
        const fileImage = new osparc.ui.basic.Thumbnail(imageSrc).set({
          padding: 12
        });
        this.__inputOutputLayout.addAt(fileImage, 1, {
          flex: 1
        });
      }
      this.fireEvent("nodeMoving");
    },

    getInputPort: function() {
      return this.__inputLayout;
    },

    getOutputPort: function() {
      return this.__outputLayout;
    },

    __createUIPorts: function(isInput, ports) {
      // Always create ports if node is a container
      if (!this.getNode().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      const portLabel = this.__createUIPortLabel(isInput);
      const label = {
        isInput: isInput,
        ui: portLabel
      };
      if (isInput) {
        this.getNode().getStatus().bind("dependencies", portLabel, "textColor", {
          converter: dependencies => {
            if (dependencies !== null) {
              return osparc.utils.StatusUI.getColor(dependencies.length ? "modified" : "ready");
            }
            return osparc.utils.StatusUI.getColor();
          }
        });
      } else {
        this.getNode().getStatus().bind("output", portLabel, "textColor", {
          converter: output => {
            switch (output) {
              case "up-to-date":
                return osparc.utils.StatusUI.getColor("ready");
              case "out-of-date":
              case "busy":
                return osparc.utils.StatusUI.getColor("modified");
              case "not-available":
              default:
                return osparc.utils.StatusUI.getColor();
            }
          }
        });
      }
      label.ui.isInput = isInput;
      this.__addDragDropMechanism(label.ui, isInput);
      if (isInput) {
        this.__inputLayout = label;
        this.__inputOutputLayout.addAt(label.ui, 0, {
          flex: 1
        });
      } else {
        this.__outputLayout = label;
        const nElements = this.__inputOutputLayout.getChildren().length;
        this.__inputOutputLayout.addAt(label.ui, nElements, {
          flex: 1
        });
        label.ui.addListener("tap", e => {
          this.__openNodeDataManager();
          e.preventDefault();
        }, this);
      }
    },

    __createUIPortLabel: function(isInput) {
      const labelText = isInput ? "in" : "out";
      const alignX = isInput ? "left" : "right";
      const uiPort = new qx.ui.basic.Label(labelText).set({
        height: this.self(arguments).PORT_HEIGHT,
        draggable: true,
        droppable: true,
        textAlign: alignX,
        allowGrowX: true,
        paddingLeft: 5,
        paddingRight: 5
      });
      uiPort.setCursor("pointer");
      return uiPort;
    },

    __addDragDropMechanism: function(uiPort, isInput) {
      [
        ["dragstart", "edgeDragStart"],
        ["dragover", "edgeDragOver"],
        ["drop", "edgeDrop"],
        ["dragend", "edgeDragEnd"]
      ].forEach(eventPair => {
        uiPort.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            nodeId: this.getNodeId(),
            isInput: isInput
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    __openNodeDataManager: function() {
      const nodeDataManager = new osparc.component.widget.NodeDataManager(this.getNode());
      const win = osparc.ui.window.Window.popUpInWindow(nodeDataManager, this.getNode().getLabel(), 900, 600).set({
        appearance: "service-window"
      });
      const closeBtn = win.getChildControl("close-button");
      osparc.utils.Utils.setIdToWidget(closeBtn, "nodeDataManagerCloseBtn");
    },

    getEdgePoint: function(port) {
      const bounds = this.getCurrentBounds();
      const captionHeight = Math.max(this.getChildControl("captionbar").getSizeHint().height, this.self().captionHeight());
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width;
      let y = bounds.top + captionHeight + this.self(arguments).PORT_HEIGHT/2 + 1;
      if (this.__thumbnail) {
        y += this.__thumbnail.getBounds().height;
      }
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

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }
      const sideBarWidth = this.__dragRange.left;
      const navigationBarHeight = this.__dragRange.top;
      const native = e.getNativeEvent();
      const x = native.clientX + this.__dragLeft - sideBarWidth;
      const y = native.clientY + this.__dragTop - navigationBarHeight;
      const coords = this.__scaleCoordinates(x, y);
      const insets = this.getLayoutParent().getInsets();
      this.setDomPosition(coords.x - (insets.left || 0), coords.y - (insets.top || 0));
      e.stopPropagation();

      this.getNode().setPosition(coords);
      this.fireEvent("nodeMoving");
    },

    // override qx.ui.core.MMovable
    _onMovePointerUp : function(e) {
      if (this.hasListener("roll")) {
        this.removeListener("roll", this._onMoveRoll, this);
      }

      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }

      this._onMovePointerMove(e);

      this.fireEvent("nodeStoppedMoving");

      // Remove drag state
      this.removeState("move");

      this.releaseCapture();

      e.stopPropagation();
    },

    _applyThumbnail: function(thumbnail, oldThumbnail) {
      if (oldThumbnail !== null) {
        this.removeAt(0);
      }
      if (osparc.utils.Utils.isUrl(thumbnail)) {
        this.__thumbnail = new qx.ui.basic.Image(thumbnail).set({
          height: 100,
          allowShrinkX: true,
          scale: true
        });
      } else {
        this.__thumbnail = new qx.ui.embed.Html(thumbnail).set({
          height: 100
        });
      }
      this.addAt(this.__thumbnail, 0);
    },

    _filter: function() {
      this.setOpacity(0.4);
    },

    _unfilter: function() {
      this.setOpacity(1);
    },

    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.getNode().getLabel()
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      if (data.tags && data.tags.length) {
        const category = this.getNode().getMetaData().category || "";
        const type = this.getNode().getMetaData().type || "";
        if (!data.tags.includes(osparc.utils.Utils.capitalize(category.trim())) && !data.tags.includes(osparc.utils.Utils.capitalize(type.trim()))) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
