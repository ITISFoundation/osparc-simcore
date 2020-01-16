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

    this.set({
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      width: this.self(arguments).NodeWidth,
      maxWidth: this.self(arguments).NodeWidth,
      minWidth: this.self(arguments).NodeWidth,
      contentPadding: 0
    });

    this.setNode(node);

    this.__createNodeLayout();

    this.subscribeToFilterGroup("workbench");
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
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
    "nodeMoving": "qx.event.type.Event"
  },

  statics: {
    NodeWidth: 200,
    NodeHeight: 80,
    PortHeight: 16
  },

  members: {
    __inputPortLayout: null,
    __outputPortLayout: null,
    __inputPort: null,
    __outputPort: null,
    __progressBar: null,
    __thumbnail: null,
    __status: null,


    getNodeId: function() {
      return this.getNode().getNodeId();
    },

    getMetaData: function() {
      return this.getNode().getMetaData();
    },

    getCaptionBar: function() {
      return this.getChildControl("captionbar");
    },

    setTriSelected: function(triState) {
      switch (triState) {
        case 0:
          // unselect
          this.resetBackgroundColor();
          this.getCaptionBar().resetBackgroundColor();
          break;
        case 1:
          // semiselect
          this.setBackgroundColor("node-semiselected-backgroud");
          this.getCaptionBar().setBackgroundColor("node-semiselected-backgroud");
          break;
        case 2:
          // select
          this.setBackgroundColor("node-selected-backgroud");
          this.getCaptionBar().setBackgroundColor("node-selected-backgroud");
          break;
      }
    },

    __createNodeLayout: function() {
      this.setLayout(new qx.ui.layout.VBox());

      if (this.getNode().getThumbnail()) {
        this.setThumbnail(this.getNode().getThumbnail());
      }

      let inputsOutputsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this.add(inputsOutputsLayout, {
        flex: 1
      });

      let inputsBox = new qx.ui.layout.VBox(5);
      this.__inputPortLayout = new qx.ui.container.Composite(inputsBox).set({
        marginLeft: 4
      });
      inputsOutputsLayout.add(this.__inputPortLayout, {
        width: "50%"
      });

      let outputsBox = new qx.ui.layout.VBox(5);
      this.__outputPortLayout = new qx.ui.container.Composite(outputsBox).set({
        marginRight: 4
      });
      inputsOutputsLayout.add(this.__outputPortLayout, {
        width: "50%"
      });

      this.add(this.__createChipContainer());

      if (this.getNode().isComputational()) {
        this.__progressBar = new qx.ui.indicator.ProgressBar().set({
          height: 10,
          margin: 4
        });
        this.add(this.__progressBar);
      } else if (this.getNode().isDynamic()) {
        this.__addStatusIndicator();
      }
    },

    populateNodeLayout: function() {
      const node = this.getNode();
      node.bind("label", this, "caption");
      if (node.isContainer()) {
        this.setIcon("@FontAwesome5Solid/folder-open/14");
      }
      this.__inputPort = null;
      this.__outputPort = null;
      const metaData = node.getMetaData();
      if (metaData) {
        this.__createUIPorts(true, metaData.inputs);
        this.__createUIPorts(false, metaData.outputs);
      }
      if (node.isComputational()) {
        node.bind("progress", this.__progressBar, "value");
      }
    },

    getInputPort: function() {
      return this.__inputPort;
    },

    getOutputPort: function() {
      return this.__outputPort;
    },

    __createUIPorts: function(isInput, ports) {
      // Always create ports if node is a container
      if (!this.getNode().isContainer() && Object.keys(ports).length < 1) {
        return;
      }
      let portUI = this.__createUIPort(isInput);
      this.__createUIPortConnections(portUI, isInput);
      let label = {
        isInput: isInput,
        ui: portUI
      };
      label.ui.isInput = isInput;
      if (isInput) {
        this.__inputPort = label;
        this.__inputPortLayout.add(label.ui);
      } else {
        this.__outputPort = label;
        this.__outputPortLayout.add(label.ui);
      }
    },

    __createUIPort: function(isInput) {
      const labelText = (isInput) ? "in" : "out";
      const alignX = (isInput) ? "left" : "right";
      let uiPort = new qx.ui.basic.Atom(labelText).set({
        height: this.self(arguments).PortHeight,
        draggable: true,
        droppable: true,
        alignX: alignX,
        allowGrowX: false
      });
      return uiPort;
    },

    __createUIPortConnections: function(uiPort, isInput) {
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

    getEdgePoint: function(port) {
      const bounds = this.getCurrentBounds();
      const captionHeight = osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().minHeight;
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width;
      let y = bounds.top + captionHeight + this.self(arguments).PortHeight/2 + 1;
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

    __createChipContainer: function() {
      const chipContainer = this.__chipContainer = new qx.ui.container.Composite(new qx.ui.layout.Flow(3, 3)).set({
        margin: [3, 4]
      });
      const category = this.getNode().isContainer() ? null : osparc.utils.Services.getCategory(this.getNode().getMetaData().category);
      const nodeType = this.getNode().isContainer() ? "container" : this.getNode().getMetaData().type;
      const type = osparc.utils.Services.getType(nodeType);
      if (type) {
        chipContainer.add(new osparc.ui.basic.Chip(type.label, type.icon + "12"));
      }
      if (category) {
        chipContainer.add(new osparc.ui.basic.Chip(category.label, category.icon + "12"));
      }
      return chipContainer;
    },

    __addStatusIndicator: function() {
      this.__status = new osparc.component.service.NodeStatus(this.getNode());
      this.__chipContainer.add(this.__status);
    },

    // override qx.ui.window.Window "move" event listener
    _onMovePointerMove: function(e) {
      this.base(arguments, e);
      if (e.getPropagationStopped() === true) {
        this.fireEvent("nodeMoving");
      }
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
        const category = this.getMetaData().category || "";
        const type = this.getMetaData().type || "";
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
