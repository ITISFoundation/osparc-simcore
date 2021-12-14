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
  extend: osparc.component.workbench.BaseNodeUI,

  /**
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(node) {
    this.base(arguments);

    this.set({
      width: this.self(arguments).NODE_WIDTH,
      maxWidth: this.self(arguments).NODE_WIDTH,
      minWidth: this.self(arguments).NODE_WIDTH
    });

    this.setNode(node);

    this._createWindowLayout();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: false
    },

    type: {
      check: ["normal", "file", "parameter", "iterator", "iterator-consumer"],
      init: "normal",
      nullable: false,
      apply: "__applyType"
    },

    thumbnail: {
      check: "String",
      nullable: true,
      apply: "_applyThumbnail"
    }
  },

  statics: {
    NODE_WIDTH: 180,
    NODE_HEIGHT: 80,
    CIRCLED_RADIUS: 16
  },

  members: {
    __progressBar: null,
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
            nodeType = "iterator-consumer";
          }
          const type = osparc.utils.Services.getType(nodeType);
          if (type) {
            const chip = new osparc.ui.basic.Chip().set({
              icon: type.icon + "14",
              toolTipText: type.label
            });
            control.add(chip);
          }
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
      }
      return control || this.base(arguments, id);
    },

    // overridden
    _createWindowLayout: function() {
      const node = this.getNode();
      if (node.getThumbnail()) {
        this.setThumbnail(node.getThumbnail());
      }
      const chipContainer = this.getChildControl("chips");
      if (node.isComputational() || node.isFilePicker() || node.isIterator()) {
        this.__progressBar = this.getChildControl("progress");
      }

      const nodeStatus = new osparc.ui.basic.NodeStatusUI(node);
      chipContainer.add(nodeStatus);
    },

    populateNodeLayout: function(svgWorkbenchCanvas) {
      const node = this.getNode();
      node.bind("label", this, "caption", {
        onUpdate: () => {
          setTimeout(() => this.fireEvent("nodeMoving"), 50);
        }
      });
      const metaData = node.getMetaData();
      this._createPorts(true, Boolean((metaData && metaData.inputs && Object.keys(metaData.inputs).length) || this.getNode().isContainer()));
      this._createPorts(false, Boolean((metaData && metaData.outputs && Object.keys(metaData.outputs).length) || this.getNode().isContainer()));
      if (node.isComputational()) {
        node.getStatus().bind("progress", this.__progressBar, "value", {
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
        this.setType("iterator-consumer");
      }
    },

    __hideExtraElements: function() {
      const chipContainer = this.getChildControl("chips");
      chipContainer.exclude();

      if (this.__progressBar) {
        this.__progressBar.exclude();
      }

      if (this._inputLayout && "ui" in this._inputLayout) {
        this._inputLayout.exclude();
      }
    },

    __applyType: function(type) {
      switch (type) {
        case "file":
          this.__checkTurnIntoFileUI();
          break;
        case "parameter":
          this.__turnIntoParameterUI();
          break;
        case "iterator":
          this.__turnIntoIteratorUI();
          break;
        case "iterator-consumer":
          this.__turnIntoProbeUI();
          break;
      }
    },

    __turnIntoCircledUI: function(width) {
      this.set({
        width: width,
        maxWidth: width,
        minWidth: width,
        minHeight: 60
      });
      this.getContentElement().setStyles({
        "border-radius": this.self().CIRCLED_RADIUS+"px"
      });
    },

    __checkTurnIntoFileUI: function() {
      const outputs = this.getNode().getOutputs();
      if ([null, ""].includes(osparc.file.FilePicker.getOutput(outputs))) {
        this.getNode().addListener("changeOutputs", () => {
          this.__checkTurnIntoFileUI();
        }, this);
      } else {
        this.__turnIntoFileUI();
      }
    },

    __turnIntoFileUI: function() {
      const width = 120;
      this.__turnIntoCircledUI(width);
      this.__hideExtraElements();

      // two lines
      const title = this.getChildControl("title");
      title.set({
        wrap: true,
        maxHeight: 28,
        minWidth: width-16,
        maxWidth: width-16
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
      this.fireEvent("nodeMoving");
    },

    __turnIntoParameterUI: function() {
      const width = 100;
      this.__turnIntoCircledUI(width);
      this.__hideExtraElements();

      const label = new qx.ui.basic.Label().set({
        font: "text-18",
        paddingTop: 6
      });
      this.add(label, {
        row: 0,
        column: 1
      });

      this.getNode().bind("outputs", label, "value", {
        converter: outputs => {
          if ("out_1" in outputs && "value" in outputs["out_1"]) {
            return String(outputs["out_1"]["value"]);
          }
          return "";
        }
      });
      this.fireEvent("nodeMoving");
    },

    __turnIntoIteratorUI: function() {
      const width = 150;
      const height = 69;
      this.__turnIntoCircledUI(width, this.self().CIRCLED_RADIUS);

      if (this.__svgWorkbenchCanvas) {
        const nShadows = 2;
        this.shadows = [];
        for (let i=0; i<nShadows; i++) {
          const nodeUIShadow = this.__svgWorkbenchCanvas.drawNodeUI(width, height, this.self().CIRCLED_RADIUS);
          this.shadows.push(nodeUIShadow);
        }
      }

      this.__addIterationValue();
    },

    __addIterationValue: function() {
      const label = new qx.ui.basic.Label().set({
        paddingLeft: 5,
        font: "text-18"
      });
      const chipContainer = this.getChildControl("chips");
      chipContainer.add(label);
      this.getNode().bind("outputs", label, "value", {
        converter: outputs => {
          const portKey = "out_1";
          if (portKey in outputs && "value" in outputs[portKey]) {
            return String(outputs[portKey]["value"]);
          }
          return "";
        }
      });
    },

    __turnIntoProbeUI: function() {
      const width = 150;
      this.__turnIntoCircledUI(width, this.self().CIRCLED_RADIUS);

      const label = new qx.ui.basic.Label().set({
        paddingLeft: 5,
        font: "text-18"
      });
      const chipContainer = this.getChildControl("chips");
      chipContainer.add(label);

      this.getNode().getPropsForm().addListener("linkFieldModified", () => this.__setProbeValue(label), this);
      this.__setProbeValue(label);
    },

    __setProbeValue: function(label) {
      const link = this.getNode().getPropsForm().getLink("in_1");
      if (link && "nodeUuid" in link) {
        const inputNodeId = link["nodeUuid"];
        const portKey = link["output"];
        const inputNode = this.getNode().getWorkbench().getNode(inputNodeId);
        if (inputNode) {
          inputNode.bind("outputs", label, "value", {
            converter: outputs => {
              if (portKey in outputs && "value" in outputs[portKey]) {
                return String(outputs[portKey]["value"]);
              }
              return "";
            }
          });
        }
      } else {
        label.setValue("");
      }
    },

    // overridden
    _createPorts: function(isInput, draw) {
      if (draw === false) {
        this._createPort(isInput, true);
        return;
      }
      const port = this._createPort(isInput);
      port.addListener("mouseover", () => {
        port.setSource(osparc.component.workbench.BaseNodeUI.NODE_CONNECTED);
      }, this);
      port.addListener("mouseout", () => {
        const isConnected = isInput ? this.getNode().getInputConnected() : this.getNode().getOutputConnected();
        port.set({
          source: isConnected ? osparc.component.workbench.BaseNodeUI.NODE_CONNECTED : osparc.component.workbench.BaseNodeUI.NODE_DISCONNECTED
        });
      }, this);
      if (isInput) {
        this.getNode().getStatus().bind("dependencies", port, "textColor", {
          converter: dependencies => {
            if (dependencies !== null) {
              return osparc.utils.StatusUI.getColor(dependencies.length ? "modified" : "ready");
            }
            return osparc.utils.StatusUI.getColor();
          }
        });
        this.getNode().bind("inputConnected", port, "source", {
          converter: isConnected => isConnected ? osparc.component.workbench.BaseNodeUI.NODE_CONNECTED : osparc.component.workbench.BaseNodeUI.NODE_DISCONNECTED
        });
      } else {
        this.getNode().getStatus().bind("output", port, "textColor", {
          converter: output => osparc.utils.StatusUI.getColor(output)
        });
        this.getNode().bind("outputConnected", port, "source", {
          converter: isConnected => isConnected ? osparc.component.workbench.BaseNodeUI.NODE_CONNECTED : osparc.component.workbench.BaseNodeUI.NODE_DISCONNECTED
        });
      }

      this._addDragDropMechanism(port, isInput);
    },

    // overridden
    _createDragDropEventData: function(e, isInput) {
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
        this.__thumbnail = new osparc.ui.basic.Thumbnail(thumbnail).set({
          padding: 12
        });
      }
      this.add(this.__thumbnail, {
        row: 0,
        column: 1
      });
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

    // implement osparc.component.filter.IFilterable
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
